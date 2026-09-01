from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet, ChatSessionViewSet, QuizViewSet, StudyGuideViewSet

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'sessions', ChatSessionViewSet, basename='session')
router.register(r'quizzes', QuizViewSet, basename='quiz')
router.register(r'study-guides', StudyGuideViewSet, basename='study-guide')

urlpatterns = router.urls