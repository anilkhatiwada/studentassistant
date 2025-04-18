from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import (
    Department, Faculty, Student, AcademicProgram, Course,
    ProgramCourse, Semester, CourseOffering, Enrollment,
    Transcript, Announcement, Building, Room
)
from .serializers import (
    UserSerializer, DepartmentSerializer, FacultySerializer,
    StudentSerializer, AcademicProgramSerializer, CourseSerializer,
    ProgramCourseSerializer, SemesterSerializer, CourseOfferingSerializer,
    EnrollmentSerializer, TranscriptSerializer, AnnouncementSerializer,
    BuildingSerializer, RoomSerializer,
    SimpleDepartmentSerializer, SimpleFacultySerializer,
    SimpleAcademicProgramSerializer, SimpleCourseSerializer,
    SimpleSemesterSerializer, SimpleStudentSerializer
)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all().order_by('name')
    serializer_class = DepartmentSerializer

    def get_serializer_class(self):
        if self.action in ['list']:
            return SimpleDepartmentSerializer
        return DepartmentSerializer

class FacultyViewSet(viewsets.ModelViewSet):
    queryset = Faculty.objects.all().order_by('user__last_name', 'user__first_name')
    serializer_class = FacultySerializer

    def get_serializer_class(self):
        if self.action in ['list']:
            return SimpleFacultySerializer
        return FacultySerializer

    @action(detail=True, methods=['get'])
    def advisees(self, request, pk=None):
        faculty = self.get_object()
        advisees = Student.objects.filter(advisor=faculty)
        serializer = SimpleStudentSerializer(advisees, many=True)
        return Response(serializer.data)

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all().order_by('user__last_name', 'user__first_name')
    serializer_class = StudentSerializer

    def get_serializer_class(self):
        if self.action in ['list']:
            return SimpleStudentSerializer
        return StudentSerializer

    @action(detail=True, methods=['get'])
    def transcript(self, request, pk=None):
        student = self.get_object()
        transcript, created = Transcript.objects.get_or_create(student=student)
        serializer = TranscriptSerializer(transcript)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def enrollments(self, request, pk=None):
        student = self.get_object()
        enrollments = Enrollment.objects.filter(student=student)
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)

class AcademicProgramViewSet(viewsets.ModelViewSet):
    queryset = AcademicProgram.objects.all().order_by('department', 'name')
    serializer_class = AcademicProgramSerializer

    def get_serializer_class(self):
        if self.action in ['list']:
            return SimpleAcademicProgramSerializer
        return AcademicProgramSerializer

    @action(detail=True, methods=['get'])
    def courses(self, request, pk=None):
        program = self.get_object()
        program_courses = ProgramCourse.objects.filter(program=program)
        serializer = ProgramCourseSerializer(program_courses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        program = self.get_object()
        students = Student.objects.filter(current_program=program)
        serializer = SimpleStudentSerializer(students, many=True)
        return Response(serializer.data)

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all().order_by('code')
    serializer_class = CourseSerializer

    def get_serializer_class(self):
        if self.action in ['list']:
            return SimpleCourseSerializer
        return CourseSerializer

    @action(detail=True, methods=['get'])
    def offerings(self, request, pk=None):
        course = self.get_object()
        offerings = CourseOffering.objects.filter(course=course)
        serializer = CourseOfferingSerializer(offerings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def prerequisites(self, request, pk=None):
        course = self.get_object()
        prerequisites = course.prerequisites.all()
        serializer = SimpleCourseSerializer(prerequisites, many=True)
        return Response(serializer.data)

class ProgramCourseViewSet(viewsets.ModelViewSet):
    queryset = ProgramCourse.objects.all()
    serializer_class = ProgramCourseSerializer

class SemesterViewSet(viewsets.ModelViewSet):
    queryset = Semester.objects.all().order_by('-year', 'season')
    serializer_class = SemesterSerializer

    def get_serializer_class(self):
        if self.action in ['list']:
            return SimpleSemesterSerializer
        return SemesterSerializer

    @action(detail=False, methods=['get'])
    def current(self, request):
        current_semester = Semester.objects.filter(is_current=True).first()
        if not current_semester:
            return Response({'detail': 'No current semester set'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(current_semester)
        return Response(serializer.data)

class CourseOfferingViewSet(viewsets.ModelViewSet):
    queryset = CourseOffering.objects.all().order_by('course', 'section')
    serializer_class = CourseOfferingSerializer

    @action(detail=True, methods=['get'])
    def enrollments(self, request, pk=None):
        offering = self.get_object()
        enrollments = Enrollment.objects.filter(course_offering=offering)
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        offering = self.get_object()
        student_id = request.data.get('student_id')
        
        if not student_id:
            return Response({'error': 'student_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if Enrollment.objects.filter(student=student, course_offering=offering).exists():
            return Response({'error': 'Student already enrolled'}, status=status.HTTP_400_BAD_REQUEST)
        
        enrollment = Enrollment.objects.create(
            student=student,
            course_offering=offering,
            credits_attempted=offering.course.credits,
            status='registered'
        )
        
        offering.enrolled += 1
        offering.save()
        
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class EnrollmentViewSet(viewsets.ModelViewSet):
    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer

    @action(detail=True, methods=['patch'])
    def update_grade(self, request, pk=None):
        enrollment = self.get_object()
        grade = request.data.get('grade')
        
        if not grade:
            return Response({'error': 'grade is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        enrollment.grade = grade
        enrollment.save()
        
        # Update transcript
        transcript = Transcript.objects.get(student=enrollment.student)
        transcript.update_transcript()
        
        serializer = self.get_serializer(enrollment)
        return Response(serializer.data)

class TranscriptViewSet(mixins.RetrieveModelMixin,
                      mixins.ListModelMixin,
                      viewsets.GenericViewSet):
    queryset = Transcript.objects.all()
    serializer_class = TranscriptSerializer

class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.all().order_by('-publish_date')
    serializer_class = AnnouncementSerializer

class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all().order_by('name')
    serializer_class = BuildingSerializer

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all().order_by('building', 'room_number')
    serializer_class = RoomSerializer