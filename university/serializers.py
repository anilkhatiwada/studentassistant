from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Department, Faculty, Student, AcademicProgram, Course,
    ProgramCourse, Semester, CourseOffering, Enrollment,
    Transcript, Announcement, Building, Room
)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class DepartmentSerializer(serializers.ModelSerializer):
    head_of_department_name = serializers.CharField(source='head_of_department.user.get_full_name', read_only=True)
    
    class Meta:
        model = Department
        fields = [
            'id', 'name', 'code', 'description', 'established_date',
            'website', 'location', 'contact_email', 'head_of_department',
            'head_of_department_name'
        ]

class FacultySerializer(serializers.ModelSerializer):
    user = UserSerializer()
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True
    )
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Faculty
        fields = [
            'id', 'user', 'department', 'department_id', 'rank',
            'office_location', 'office_hours', 'phone', 'hire_date',
            'research_interests', 'bio', 'profile_picture', 'full_name'
        ]
        read_only_fields = ['profile_picture']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create_user(**user_data)
        faculty = Faculty.objects.create(user=user, **validated_data)
        return faculty
    
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class AcademicProgramSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True
    )
    
    class Meta:
        model = AcademicProgram
        fields = [
            'id', 'name', 'code', 'description', 'department', 'department_id',
            'program_type', 'degree', 'total_credits_required', 'duration_years',
            'is_active', 'created_date', 'updated_date'
        ]

class StudentSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    current_program = AcademicProgramSerializer(read_only=True)
    current_program_id = serializers.PrimaryKeyRelatedField(
        queryset=AcademicProgram.objects.all(),
        source='current_program',
        write_only=True,
        allow_null=True
    )
    advisor = FacultySerializer(read_only=True)
    advisor_id = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.all(),
        source='advisor',
        write_only=True,
        allow_null=True
    )
    full_name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = [
            'id', 'user', 'student_id', 'date_of_birth', 'admission_date',
            'expected_graduation', 'current_program', 'current_program_id',
            'degree_type', 'status', 'advisor', 'advisor_id', 'gpa',
            'profile_picture', 'full_name', 'age'
        ]
        read_only_fields = ['gpa', 'profile_picture']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    
    def get_age(self, obj):
        from datetime import date
        today = date.today()
        return today.year - obj.date_of_birth.year - (
            (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
        )
    
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create_user(**user_data)
        student = Student.objects.create(user=user, **validated_data)
        return student
    
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class CourseSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True
    )
    prerequisites = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        many=True,
        required=False
    )
    
    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'department', 'department_id',
            'credits', 'level', 'prerequisites', 'is_core', 'is_active',
            'learning_outcomes', 'syllabus'
        ]

class ProgramCourseSerializer(serializers.ModelSerializer):
    program = AcademicProgramSerializer(read_only=True)
    program_id = serializers.PrimaryKeyRelatedField(
        queryset=AcademicProgram.objects.all(),
        source='program',
        write_only=True
    )
    course = CourseSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        source='course',
        write_only=True
    )
    
    class Meta:
        model = ProgramCourse
        fields = [
            'id', 'program', 'program_id', 'course', 'course_id',
            'is_required', 'semester_offered'
        ]

class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = [
            'id', 'name', 'code', 'year', 'season', 'start_date', 'end_date',
            'registration_start', 'registration_end', 'is_current'
        ]

class CourseOfferingSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        source='course',
        write_only=True
    )
    semester = SemesterSerializer(read_only=True)
    semester_id = serializers.PrimaryKeyRelatedField(
        queryset=Semester.objects.all(),
        source='semester',
        write_only=True
    )
    instructor = FacultySerializer(read_only=True)
    instructor_id = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.all(),
        source='instructor',
        write_only=True,
        allow_null=True
    )
    
    class Meta:
        model = CourseOffering
        fields = [
            'id', 'course', 'course_id', 'semester', 'semester_id',
            'instructor', 'instructor_id', 'section', 'capacity', 'enrolled',
            'classroom', 'schedule', 'is_active'
        ]

class EnrollmentSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    student_id = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(),
        source='student',
        write_only=True
    )
    course_offering = CourseOfferingSerializer(read_only=True)
    course_offering_id = serializers.PrimaryKeyRelatedField(
        queryset=CourseOffering.objects.all(),
        source='course_offering',
        write_only=True
    )
    
    class Meta:
        model = Enrollment
        fields = [
            'id', 'student', 'student_id', 'course_offering', 'course_offering_id',
            'enrollment_date', 'grade', 'status', 'credits_attempted',
            'credits_earned', 'is_audit'
        ]
        read_only_fields = ['enrollment_date']

class TranscriptSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    
    class Meta:
        model = Transcript
        fields = [
            'id', 'student', 'total_credits_attempted', 'total_credits_earned',
            'cumulative_gpa', 'last_updated'
        ]
        read_only_fields = fields

class AnnouncementSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    
    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'content', 'author', 'publish_date',
            'expiration_date', 'is_urgent', 'target_audience'
        ]
        read_only_fields = ['author', 'publish_date']

class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = ['id', 'name', 'code', 'location', 'description', 'image']
        read_only_fields = ['image']

class RoomSerializer(serializers.ModelSerializer):
    building = BuildingSerializer(read_only=True)
    building_id = serializers.PrimaryKeyRelatedField(
        queryset=Building.objects.all(),
        source='building',
        write_only=True
    )
    
    class Meta:
        model = Room
        fields = [
            'id', 'building', 'building_id', 'room_number', 'capacity',
            'room_type', 'features'
        ]

# Simplified serializers for nested representations
class SimpleDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'code']

class SimpleFacultySerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.get_full_name')
    
    class Meta:
        model = Faculty
        fields = ['id', 'name']

class SimpleAcademicProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicProgram
        fields = ['id', 'name', 'code']

class SimpleCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'code', 'title']

class SimpleSemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ['id', 'name', 'code', 'year', 'season']

class SimpleStudentSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.get_full_name')
    
    class Meta:
        model = Student
        fields = ['id', 'name', 'student_id']