import uuid
from django.db import models
from django.contrib.auth.models import User


class Document(models.Model):
    """A document uploaded by a user to be used as RAG context."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    file = models.FileField(upload_to='documents/')
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    chunk_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Each document gets its own Chroma "collection" so retrieval can be
    # scoped to one document or merged across many.
    @property
    def collection_name(self):
        return f"doc_{self.id.hex}"

    def __str__(self):
        return self.title or str(self.file)


class ChatSession(models.Model):
    """A conversation thread, optionally scoped to one or more documents."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    documents = models.ManyToManyField(Document, related_name='sessions', blank=True)
    title = models.CharField(max_length=255, default='New Chat')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    # Stores which document chunks were used to answer (for citation display)
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"


class Quiz(models.Model):
    """"A set of auto-generated MCQ Question for one document."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    document=models.ForeignKey(Document,on_delete=models.CASCADE,related_name='quizzes')
    created_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quiz for {self.document}"


class QuizQuestion(models.Model):
    """A single Question MCQ belonging to a Quiz."""

    quiz=models.ForeignKey(Quiz,on_delete=models.CASCADE,related_name='questions')
    question_text=models.TextField()
    option_a=models.CharField(max_length=500)
    option_b=models.CharField(max_length=500)
    option_c=models.CharField(max_length=500)
    option_d=models.CharField(max_length=500)
    correct_option=models.CharField(max_length=1) # 'A', 'B', 'C', or 'D'
    explanation=models.TextField(blank=True)


    def __str__(self):
        return f"Question for {self.quiz.document}: {self.question_text[:50]}"


class StudyGuide(models.Model):
    """A downloadable/viewable Q&A PDF generated from one document,
    in whatever language the document itself is written in."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='study_guides')
    language = models.CharField(max_length=5, default='en')  # 'en' or 'bn'
    pdf_file = models.FileField(upload_to='study_guides/')
    question_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Study guide for {self.document}"