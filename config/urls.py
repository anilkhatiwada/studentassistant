from django.urls import path, include
from rest_framework.routers import DefaultRouter
from university import views
from ai.views import university_assistant
from django.contrib import admin

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'departments', views.DepartmentViewSet)
router.register(r'faculty', views.FacultyViewSet)
router.register(r'students', views.StudentViewSet)
router.register(r'programs', views.AcademicProgramViewSet)
router.register(r'courses', views.CourseViewSet)
router.register(r'program-courses', views.ProgramCourseViewSet)
router.register(r'semesters', views.SemesterViewSet)
router.register(r'offerings', views.CourseOfferingViewSet)
router.register(r'enrollments', views.EnrollmentViewSet)
router.register(r'transcripts', views.TranscriptViewSet)
router.register(r'announcements', views.AnnouncementViewSet)
router.register(r'buildings', views.BuildingViewSet)
router.register(r'rooms', views.RoomViewSet)


# Additional custom URLs that don't fit the ViewSet pattern
urlpatterns = [

    # Admin site
    path('admin/', admin.site.urls),
    # API root
    path('', include(router.urls)),
    
    # Authentication endpoints
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
    
    # Custom endpoints
    path('current-semester/', views.SemesterViewSet.as_view({'get': 'current'}), name='current-semester'),
    
    # Faculty-specific endpoints
    path('faculty/<int:pk>/advisees/', views.FacultyViewSet.as_view({'get': 'advisees'}), name='faculty-advisees'),
    
    # Student-specific endpoints
    path('students/<int:pk>/transcript/', views.StudentViewSet.as_view({'get': 'transcript'}), name='student-transcript'),
    path('students/<int:pk>/enrollments/', views.StudentViewSet.as_view({'get': 'enrollments'}), name='student-enrollments'),
    
    # Program-specific endpoints
    path('programs/<int:pk>/courses/', views.AcademicProgramViewSet.as_view({'get': 'courses'}), name='program-courses'),
    path('programs/<int:pk>/students/', views.AcademicProgramViewSet.as_view({'get': 'students'}), name='program-students'),
    
    # Course-specific endpoints
    path('courses/<int:pk>/offerings/', views.CourseViewSet.as_view({'get': 'offerings'}), name='course-offerings'),
    path('courses/<int:pk>/prerequisites/', views.CourseViewSet.as_view({'get': 'prerequisites'}), name='course-prerequisites'),
    
    # Course offering endpoints
    path('offerings/<int:pk>/enrollments/', views.CourseOfferingViewSet.as_view({'get': 'enrollments'}), name='offering-enrollments'),
    path('offerings/<int:pk>/enroll/', views.CourseOfferingViewSet.as_view({'post': 'enroll'}), name='offering-enroll'),
    
    # Enrollment endpoints
    path('enrollments/<int:pk>/update-grade/', views.EnrollmentViewSet.as_view({'patch': 'update_grade'}), name='enrollment-update-grade'),
]

# Add login/logout endpoints for the browsable API
urlpatterns += [
    path('api-auth/', include('rest_framework.urls')),
    path('assistant/', university_assistant, name='university-assistant'),
]