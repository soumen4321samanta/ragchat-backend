from rest_framework import serializers
from .models import Document, ChatSession, Message, Quiz, QuizQuestion, StudyGuide

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'status', 'chunk_count', 'error_message', 'created_at']
        read_only_fields = ['id', 'status', 'chunk_count', 'error_message', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'sources', 'created_at']
        read_only_fields = ['id', 'sources', 'created_at']


class ChatSessionSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    document_ids = serializers.PrimaryKeyRelatedField(
        source='documents', queryset=Document.objects.all(), many=True, required=False
    )

    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'document_ids', 'messages', 'created_at']
        read_only_fields = ['id', 'created_at']


class AskQuestionSerializer(serializers.Serializer):
    question = serializers.CharField()


class QuizQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model=QuizQuestion
        fields=[
            'id',
            'question_text',
            'option_a',
            'option_b',
            'option_c',
            'option_d',
            'correct_option',
            'explanation',
        ]

class QuizSerializer(serializers.ModelSerializer):
    questions=QuizQuestionSerializer(many=True, read_only=True)

    class Meta:
        model=Quiz
        fields=[
            'id','document','created_at','questions'
        ]


class GenerateQuizSerializer(serializers.Serializer):
    num_questions=serializers.IntegerField(required=False,default=5,min_value=1,max_value=15)




class StudyGuideSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyGuide
        fields = ['id', 'document', 'language', 'pdf_file', 'question_count', 'created_at']


class GenerateStudyGuideSerializer(serializers.Serializer):
    num_questions = serializers.IntegerField(required=False, default=8, min_value=1, max_value=20)