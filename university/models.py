from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class Department(models.Model):
    """Model representing an academic department"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    established_date = models.DateField(null=True, blank=True)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=100)
    contact_email = models.EmailField()
    head_of_department = models.ForeignKey(
        'Faculty',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_department'
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Faculty(models.Model):
    """Model representing a faculty member"""
    RANK_CHOICES = [
        ('ASST', 'Assistant Professor'),
        ('ASSO', 'Associate Professor'),
        ('PROF', 'Professor'),
        ('LECT', 'Lecturer'),
        ('INST', 'Instructor'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, blank=True, null=True)
    rank = models.CharField(max_length=4, choices=RANK_CHOICES)
    office_location = models.CharField(max_length=50)
    office_hours = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20)
    hire_date = models.DateField()
    research_interests = models.TextField(blank=True)
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='faculty_profiles/', blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.department.code})"

    class Meta:
        verbose_name_plural = "Faculty"
        ordering = ['user__last_name', 'user__first_name']


class Student(models.Model):
    """Model representing a student"""
    DEGREE_CHOICES = [
        ('UG', 'Undergraduate'),
        ('PG', 'Postgraduate'),
        ('PHD', 'PhD'),
    ]

    STATUS_CHOICES = [
        ('A', 'Active'),
        ('G', 'Graduated'),
        ('L', 'On Leave'),
        ('W', 'Withdrawn'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    date_of_birth = models.DateField()
    admission_date = models.DateField()
    expected_graduation = models.DateField()
    current_program = models.ForeignKey('AcademicProgram', on_delete=models.SET_NULL, null=True)
    degree_type = models.CharField(max_length=3, choices=DEGREE_CHOICES)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='A')
    advisor = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advisees'
    )
    gpa = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0.0), MaxValueValidator(4.0)])
    profile_picture = models.ImageField(upload_to='student_profiles/', blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

    class Meta:
        ordering = ['user__last_name', 'user__first_name']


class AcademicProgram(models.Model):
    """Model representing an academic program (major/minor)"""
    PROGRAM_TYPE_CHOICES = [
        ('MAJ', 'Major'),
        ('MIN', 'Minor'),
        ('CERT', 'Certificate'),
        ('DIP', 'Diploma'),
    ]

    DEGREE_CHOICES = [
        ('BA', 'Bachelor of Arts'),
        ('BS', 'Bachelor of Science'),
        ('MA', 'Master of Arts'),
        ('MS', 'Master of Science'),
        ('MBA', 'Master of Business Administration'),
        ('PHD', 'Doctor of Philosophy'),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField()
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    program_type = models.CharField(max_length=4, choices=PROGRAM_TYPE_CHOICES)
    degree = models.CharField(max_length=3, choices=DEGREE_CHOICES, blank=True, null=True)
    total_credits_required = models.PositiveSmallIntegerField()
    duration_years = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)
    created_date = models.DateField(auto_now_add=True)
    updated_date = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        ordering = ['department', 'name']


class Course(models.Model):
    """Model representing a course"""
    LEVEL_CHOICES = [
        (100, '100 Level'),
        (200, '200 Level'),
        (300, '300 Level'),
        (400, '400 Level'),
        (500, '500 Level (Graduate)'),
        (600, '600 Level (Graduate)'),
        (700, '700 Level (PhD)'),
    ]

    code = models.CharField(max_length=10, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    credits = models.PositiveSmallIntegerField(default=3)
    level = models.PositiveSmallIntegerField(choices=LEVEL_CHOICES)
    prerequisites = models.ManyToManyField('self', symmetrical=False, blank=True)
    is_core = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    learning_outcomes = models.TextField(blank=True)
    syllabus = models.FileField(upload_to='syllabi/', blank=True)

    def __str__(self):
        return f"{self.code} - {self.title}"

    class Meta:
        ordering = ['code']


class ProgramCourse(models.Model):
    """Model representing the relationship between programs and courses"""
    program = models.ForeignKey(AcademicProgram, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    is_required = models.BooleanField(default=True)
    semester_offered = models.PositiveSmallIntegerField(blank=True, null=True)  # 1-8 typically

    class Meta:
        unique_together = ('program', 'course')
        verbose_name = "Program-Course Relationship"
        verbose_name_plural = "Program-Course Relationships"

    def __str__(self):
        return f"{self.program.code} - {self.course.code}"


class Semester(models.Model):
    """Model representing an academic semester"""
    SEASON_CHOICES = [
        ('FA', 'Fall'),
        ('SP', 'Spring'),
        ('SU', 'Summer'),
        ('WI', 'Winter'),
    ]

    name = models.CharField(max_length=50)
    code = models.CharField(max_length=10, unique=True)
    year = models.PositiveSmallIntegerField()
    season = models.CharField(max_length=2, choices=SEASON_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_start = models.DateField()
    registration_end = models.DateField()
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_season_display()} {self.year}"

    class Meta:
        ordering = ['-year', 'season']
        unique_together = ('year', 'season')


class CourseOffering(models.Model):
    """Model representing a specific offering of a course in a semester"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    instructor = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, blank=True)
    section = models.CharField(max_length=10)
    capacity = models.PositiveSmallIntegerField()
    enrolled = models.PositiveSmallIntegerField(default=0)
    classroom = models.CharField(max_length=50, blank=True)
    schedule = models.CharField(max_length=100)  # e.g., "MWF 10:00-10:50"
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.course.code} - {self.section} ({self.semester})"

    class Meta:
        unique_together = ('course', 'semester', 'section')
        ordering = ['course', 'section']


class Enrollment(models.Model):
    """Model representing a student's enrollment in a course offering"""
    GRADE_CHOICES = [
        ('A', 'A'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B', 'B'),
        ('B-', 'B-'),
        ('C+', 'C+'),
        ('C', 'C'),
        ('C-', 'C-'),
        ('D+', 'D+'),
        ('D', 'D'),
        ('F', 'F'),
        ('W', 'Withdrawn'),
        ('I', 'Incomplete'),
        ('IP', 'In Progress'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course_offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE)
    enrollment_date = models.DateField(auto_now_add=True)
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True, null=True)
    status = models.CharField(max_length=20, default='registered')  # registered, dropped, completed, etc.
    credits_attempted = models.PositiveSmallIntegerField()
    credits_earned = models.PositiveSmallIntegerField(null=True, blank=True)
    is_audit = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student} in {self.course_offering}"

    class Meta:
        unique_together = ('student', 'course_offering')
        ordering = ['course_offering', 'student']


class Transcript(models.Model):
    """Model representing a student's academic record"""
    student = models.OneToOneField(Student, on_delete=models.CASCADE)
    total_credits_attempted = models.PositiveSmallIntegerField(default=0)
    total_credits_earned = models.PositiveSmallIntegerField(default=0)
    cumulative_gpa = models.FloatField(default=0.0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transcript for {self.student}"

    def update_transcript(self):
        """Method to update transcript statistics"""
        enrollments = Enrollment.objects.filter(student=self.student)
        self.total_credits_attempted = sum(e.credits_attempted for e in enrollments)
        self.total_credits_earned = sum(e.credits_earned or 0 for e in enrollments)
        
        # Calculate GPA (simplified - would need grade point conversion)
        self.save()


class Announcement(models.Model):
    """Model for university announcements"""
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    publish_date = models.DateTimeField(auto_now_add=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    is_urgent = models.BooleanField(default=False)
    target_audience = models.CharField(max_length=20, choices=[
        ('ALL', 'All'),
        ('STU', 'Students'),
        ('FAC', 'Faculty'),
        ('STA', 'Staff'),
    ], default='ALL')

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-publish_date']


class Building(models.Model):
    """Model representing campus buildings"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    location = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='building_images/', blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Room(models.Model):
    """Model representing rooms in buildings"""
    building = models.ForeignKey(Building, on_delete=models.CASCADE)
    room_number = models.CharField(max_length=20)
    capacity = models.PositiveSmallIntegerField()
    room_type = models.CharField(max_length=50)  # Classroom, Lab, Office, etc.
    features = models.TextField(blank=True)  # Projector, Whiteboard, etc.

    def __str__(self):
        return f"{self.building.code} {self.room_number}"

    class Meta:
        unique_together = ('building', 'room_number')

