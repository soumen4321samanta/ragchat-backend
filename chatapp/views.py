import os
import uuid as uuid_lib
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Document, ChatSession, Message, Quiz, QuizQuestion, StudyGuide
from .serializers import (
    DocumentSerializer, ChatSessionSerializer, AskQuestionSerializer,
    QuizSerializer, GenerateQuizSerializer,
    StudyGuideSerializer, GenerateStudyGuideSerializer,
)
from .services import document_processor, vectorstore, llm, quiz_generator, qa_generator, pdf_builder

class DocumentViewSet(viewsets.ModelViewSet):
    """
    Handles document upload + triggers the ingestion pipeline:
    extract text -> chunk -> embed -> store in ChromaDB.
    """
    queryset = Document.objects.all().order_by('-created_at')
    serializer_class = DocumentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(title=request.data.get('title', request.FILES['file'].name))

        self._ingest_document(document)

        return Response(self.get_serializer(document).data, status=status.HTTP_201_CREATED)

    def _ingest_document(self, document: Document):
        document.status = 'processing'
        document.save(update_fields=['status'])

        try:
            text = document_processor.extract_text(document.file.path)
            chunks = document_processor.chunk_text(
                text,
                chunk_size=settings.CHUNK_SIZE,
                overlap=settings.CHUNK_OVERLAP,
            )

            if not chunks:
                raise ValueError("No extractable text found in this file.")

            metadatas = [
                {"document_id": str(document.id), "chunk_index": i, "title": document.title}
                for i in range(len(chunks))
            ]

            vectorstore.add_chunks_to_collection(document.collection_name, chunks, metadatas)

            document.status = 'ready'
            document.chunk_count = len(chunks)
            document.save(update_fields=['status', 'chunk_count'])

        except Exception as e:
            document.status = 'failed'
            document.error_message = str(e)
            document.save(update_fields=['status', 'error_message'])

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        vectorstore.delete_collection(document.collection_name)
        return super().destroy(request, *args, **kwargs)

    
    @action(detail=True, methods=['post'], url_path='generate-quiz')
    def generate_quiz(self, request, pk=None):
        """
        POST /api/documents/{id}/generate-quiz/
        Body (optional): {"num_questions": 5}
        Reads the WHOLE document (all chunks, not just top-k similar ones)
        and asks the LLM to produce MCQs from it.
        """
        document = self.get_object()

        if document.status != 'ready':
            return Response(
                {"detail": f"Document is not ready yet (status: {document.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params = GenerateQuizSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        num_questions = params.validated_data['num_questions']

        # 1. Get the full document text back from ChromaDB (all chunks, in order)
        chunks = vectorstore.get_all_chunks(document.collection_name)
        if not chunks:
            return Response(
                {"detail": "No content found for this document."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        full_text = '\n\n'.join(chunks)

        # Groq has a context limit -- keep this safely within it for large docs
        MAX_CHARS = 12000
        full_text = full_text[:MAX_CHARS]

        # 2. Ask the LLM to generate MCQs as structured JSON
        try:
            mcq_data = quiz_generator.generate_mcqs(full_text, num_questions=num_questions)
        except Exception as e:
            return Response(
                {"detail": f"Failed to generate quiz: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 3. Remove any previous quiz for this document, so a document only
        #    ever has ONE (the latest) quiz -- regenerating replaces it
        #    instead of piling up duplicates.
        document.quizzes.all().delete()  # cascades and deletes their QuizQuestions too

        # 4. Save the new quiz + its questions to the database
        quiz = Quiz.objects.create(document=document)
        for item in mcq_data:
            options = item.get('options', {})
            QuizQuestion.objects.create(
                quiz=quiz,
                question_text=item.get('question', ''),
                option_a=options.get('A', ''),
                option_b=options.get('B', ''),
                option_c=options.get('C', ''),
                option_d=options.get('D', ''),
                correct_option=item.get('correct_option', 'A'),
                explanation=item.get('explanation', ''),
            )

        serializer = QuizSerializer(quiz)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



    @action(detail=True, methods=['post'], url_path='generate-study-guide')
    def generate_study_guide(self, request, pk=None):
        """
        POST /api/documents/{id}/generate-study-guide/
        Body (optional): {"num_questions": 8}
        Generates open-ended Q&A pairs from the WHOLE document, writes them
        in the same language as the document (Bengali or English), and
        renders a downloadable/viewable PDF.
        """
        document = self.get_object()

        if document.status != 'ready':
            return Response(
                {"detail": f"Document is not ready yet (status: {document.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params = GenerateStudyGuideSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        num_questions = params.validated_data['num_questions']

        chunks = vectorstore.get_all_chunks(document.collection_name)
        if not chunks:
            return Response(
                {"detail": "No content found for this document."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        full_text = '\n\n'.join(chunks)
        full_text = full_text[:12000]  # stay within the LLM's context limit

        # 1. Ask the LLM for Q&A pairs (auto-detects Bengali vs English)
        try:
            qa_pairs, language = qa_generator.generate_qa_pairs(
                full_text, num_questions=num_questions
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to generate study guide: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 2. Build the PDF file
        filename = f"study_guide_{uuid_lib.uuid4().hex}.pdf"
        relative_path = os.path.join('study_guides', filename)
        absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

        try:
            pdf_builder.build_qa_pdf(
                absolute_path,
                title=f"Study Guide: {document.title}",
                qa_pairs=qa_pairs,
                language=language,
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to build PDF: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 3. Replace any previous study guide for this document
        document.study_guides.all().delete()
        study_guide = StudyGuide.objects.create(
            document=document,
            language=language,
            pdf_file=relative_path,
            question_count=len(qa_pairs),
        )

        serializer = StudyGuideSerializer(study_guide, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    


class ChatSessionViewSet(viewsets.ModelViewSet):
    """
    Handles chat sessions and the core RAG "ask" endpoint:
    retrieve relevant chunks -> call the LLM -> save + return the answer.
    """
    queryset = ChatSession.objects.all().order_by('-created_at')
    serializer_class = ChatSessionSerializer

    @action(detail=True, methods=['post'])
    def ask(self, request, pk=None):
        session = self.get_object()
        serializer = AskQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data['question']

        # Save the user's message
        Message.objects.create(session=session, role='user', content=question)

        # 1. Retrieve relevant chunks from this session's documents
        collection_names = [doc.collection_name for doc in session.documents.all()]
        if not collection_names:
            return Response(
                {"detail": "This chat session has no documents attached yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chunks = vectorstore.query_collections(
            collection_names, question, top_k=settings.TOP_K_RESULTS
        )

        if not chunks:
            answer = "I couldn't find anything relevant in the uploaded documents."
            sources = []
        else:
            # 2. Build short chat history for follow-up questions (last 6 messages)
            history = [
                {"role": m.role if m.role == 'user' else 'assistant', "content": m.content}
                for m in session.messages.order_by('-created_at')[:6][::-1]
            ]
            # 3. Generate the answer grounded in retrieved chunks
            answer = llm.generate_answer(question, chunks, chat_history=history)
            sources = [
                {"text": c['text'][:200], "metadata": c['metadata']} for c in chunks
            ]

        assistant_message = Message.objects.create(
            session=session, role='assistant', content=answer, sources=sources
        )

        return Response({
            "answer": answer,
            "sources": sources,
            "message_id": assistant_message.id,
        })
class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only: view previously generated quizzes (created via
    DocumentViewSet.generate_quiz above)."""
    queryset = Quiz.objects.all().order_by('-created_at')
    serializer_class = QuizSerializer


class StudyGuideViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only: view previously generated study guide PDFs (created via
    DocumentViewSet.generate_study_guide above)."""
    queryset = StudyGuide.objects.all().order_by('-created_at')
    serializer_class = StudyGuideSerializer