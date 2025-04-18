from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import (
    Department, Faculty, Student, AcademicProgram, Course,
    ProgramCourse, Semester, CourseOffering, Enrollment,
    Transcript, Announcement, Building, Room
)

# Unregister the default User admin
admin.site.unregister(User)

# Custom User Admin to include faculty/student relationships
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_faculty', 'is_student')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    
    def is_faculty(self, obj):
        return hasattr(obj, 'faculty')
    is_faculty.boolean = True
    
    def is_student(self, obj):
        return hasattr(obj, 'student')
    is_student.boolean = True

admin.site.register(User, CustomUserAdmin)

# Department Admin
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head_of_department', 'established_date')
    list_filter = ('established_date',)
    search_fields = ('name', 'code', 'head_of_department__user__last_name')
    raw_id_fields = ('head_of_department',)
    ordering = ('name',)

admin.site.register(Department, DepartmentAdmin)

# Faculty Admin
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'rank', 'hire_date')
    list_filter = ('department', 'rank', 'hire_date')
    search_fields = ('user__first_name', 'user__last_name', 'department__name')
    raw_id_fields = ('user', 'department')
    ordering = ('user__last_name', 'user__first_name')

admin.site.register(Faculty, FacultyAdmin)

# Student Admin
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'current_program', 'status', 'gpa')
    list_filter = ('current_program', 'status', 'degree_type')
    search_fields = ('user__first_name', 'user__last_name', 'student_id')
    raw_id_fields = ('user', 'current_program', 'advisor')
    ordering = ('user__last_name', 'user__first_name')

admin.site.register(Student, StudentAdmin)

# Academic Program Admin
class AcademicProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department', 'program_type', 'degree', 'is_active')
    list_filter = ('department', 'program_type', 'degree', 'is_active')
    search_fields = ('name', 'code', 'department__name')
    raw_id_fields = ('department',)
    ordering = ('department', 'name')

admin.site.register(AcademicProgram, AcademicProgramAdmin)

# Course Admin
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'department', 'credits', 'level', 'is_active')
    list_filter = ('department', 'level', 'is_active', 'is_core')
    search_fields = ('code', 'title', 'department__name')
    filter_horizontal = ('prerequisites',)
    raw_id_fields = ('department',)
    ordering = ('code',)

admin.site.register(Course, CourseAdmin)

# ProgramCourse Admin
class ProgramCourseAdmin(admin.ModelAdmin):
    list_display = ('program', 'course', 'is_required', 'semester_offered')
    list_filter = ('program', 'is_required')
    search_fields = ('program__name', 'course__title')
    raw_id_fields = ('program', 'course')
    ordering = ('program', 'course')

admin.site.register(ProgramCourse, ProgramCourseAdmin)

# Semester Admin
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'year', 'season', 'start_date', 'end_date', 'is_current')
    list_filter = ('year', 'season', 'is_current')
    search_fields = ('name', 'code')
    ordering = ('-year', 'season')

admin.site.register(Semester, SemesterAdmin)

# CourseOffering Admin
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ('course', 'semester', 'section', 'instructor', 'enrolled', 'capacity', 'is_active')
    list_filter = ('semester', 'course__department', 'is_active')
    search_fields = ('course__code', 'course__title', 'instructor__user__last_name')
    raw_id_fields = ('course', 'semester', 'instructor')
    ordering = ('semester', 'course')

admin.site.register(CourseOffering, CourseOfferingAdmin)

# Enrollment Admin
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course_offering', 'grade', 'status', 'enrollment_date')
    list_filter = ('course_offering__semester', 'status', 'grade')
    search_fields = ('student__user__last_name', 'course_offering__course__title')
    raw_id_fields = ('student', 'course_offering')
    ordering = ('course_offering', 'student')

admin.site.register(Enrollment, EnrollmentAdmin)

# Transcript Admin
class TranscriptAdmin(admin.ModelAdmin):
    list_display = ('student', 'total_credits_attempted', 'total_credits_earned', 'cumulative_gpa', 'last_updated')
    search_fields = ('student__user__last_name', 'student__student_id')
    raw_id_fields = ('student',)
    ordering = ('student',)

admin.site.register(Transcript, TranscriptAdmin)

# Announcement Admin
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'publish_date', 'expiration_date', 'is_urgent', 'target_audience')
    list_filter = ('publish_date', 'is_urgent', 'target_audience')
    search_fields = ('title', 'content', 'author__last_name')
    raw_id_fields = ('author',)
    ordering = ('-publish_date',)
    date_hierarchy = 'publish_date'

admin.site.register(Announcement, AnnouncementAdmin)

# Building Admin
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location')
    search_fields = ('name', 'code', 'location')
    ordering = ('name',)

admin.site.register(Building, BuildingAdmin)

# Room Admin
class RoomAdmin(admin.ModelAdmin):
    list_display = ('building', 'room_number', 'capacity', 'room_type')
    list_filter = ('building', 'room_type')
    search_fields = ('building__name', 'room_number')
    raw_id_fields = ('building',)
    ordering = ('building', 'room_number')

admin.site.register(Room, RoomAdmin)