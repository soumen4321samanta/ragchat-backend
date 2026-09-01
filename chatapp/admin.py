from django.contrib import admin
from .models import Document, ChatSession, Message, Quiz, QuizQuestion, StudyGuide

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'status', 'chunk_count', 'created_at']
    list_filter = ['status']


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'created_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'role', 'created_at']
    list_filter = ['role']


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'created_at']


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'quiz', 'question_text', 'correct_option']



@admin.register(StudyGuide)
class StudyGuideAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'language', 'question_count', 'created_at']
    list_filter = ['language']