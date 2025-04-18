import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from faker import Faker
import random
import os
import django
from datetime import datetime, timedelta
# import setting 
from django.conf import settings


# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings)  # Replace with your project
django.setup()

from .models import (  # Replace 'my_app' with the actual name of your Django app
    Department, Faculty, Student, AcademicProgram, Course,
    ProgramCourse, Semester, CourseOffering, Enrollment,
    Transcript, Building, Room
)

# Initialize Faker for dummy data generation
fake = Faker()

# Configure Gemini API
genai.configure(api_key="AIzaSyDP3DaGFyycm-QxCg5muMgEQmd4CZySlyI")  # Replace with your actual API key

def scrape_university_website(url):
    """Scrape data from university website"""
    try:
        print(f"Scraping data from {url}...")
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        data = {
            'university_name': soup.title.text if soup.title else None,
            'programs': [],
            'departments': [],
            'courses': []
        }
        
        # Try to find programs
        program_links = soup.select('.program-list a') or soup.select('#programs a') or []
        for link in program_links[:10]:  # Limit to 10 programs
            data['programs'].append({
                'name': link.text.strip(),
                'url': link['href'] if 'href' in link.attrs else None
            })
        
        # Try to find departments
        dept_links = soup.select('.department-list a') or soup.select('#departments a') or []
        for link in dept_links[:10]:  # Limit to 10 departments
            data['departments'].append({
                'name': link.text.strip(),
                'url': link['href'] if 'href' in link.attrs else None
            })
        
        return data
    
    except Exception as e:
        print(f"Error scraping website: {e}")
        return None

def generate_dummy_data(data_type):
    """Generate realistic dummy data for missing information"""
    if data_type == 'program':
        degree_types = ['BA', 'BS', 'MA', 'MS', 'MBA', 'PhD']
        program_types = ['MAJ', 'MIN', 'CERT', 'DIP']
        return {
            'name': f"{fake.word().capitalize()} {random.choice(degree_types)} Program",
            'code': f"{random.choice(degree_types)}{random.randint(100, 999)}",
            'description': fake.paragraph(),
            'program_type': random.choice(program_types),
            'degree': random.choice(degree_types),
            'duration_years': random.choice([2, 3, 4, 5]),
            'total_credits_required': random.choice([30, 60, 90, 120])
        }
    elif data_type == 'department':
        return {
            'name': f"Department of {fake.word().capitalize()}",
            'code': fake.word().upper()[:4],
            'description': fake.paragraph(),
            'location': fake.street_address(),
            'contact_email': fake.email(),
            'website': fake.url()
        }
    elif data_type == 'course':
        levels = [100, 200, 300, 400, 500, 600]
        return {
            'code': f"{fake.word().upper()[:3]}{random.choice(levels)}",
            'title': fake.sentence(nb_words=4),
            'description': fake.paragraph(),
            'credits': random.choice([1, 2, 3, 4]),
            'level': random.choice(levels),
            'is_core': random.choice([True, False])
        }
    elif data_type == 'faculty':
        ranks = ['ASST', 'ASSO', 'PROF', 'LECT', 'INST']
        return {
            'first_name': fake.first_name(),
            'last_name': fake.last_name(),
            'rank': random.choice(ranks),
            'office_location': f"Building {random.randint(1, 10)}-{random.randint(100, 400)}",
            'phone': fake.phone_number(),
            'hire_date': fake.date_between(start_date='-20y', end_date='today'),
            'research_interests': fake.sentence()
        }
    elif data_type == 'student':
        statuses = ['A', 'G', 'L', 'W']
        degrees = ['UG', 'PG', 'PHD']
        return {
            'first_name': fake.first_name(),
            'last_name': fake.last_name(),
            'student_id': f"{random.randint(2015, 2023)}{random.randint(1000, 9999)}",
            'date_of_birth': fake.date_of_birth(minimum_age=18, maximum_age=30),
            'degree_type': random.choice(degrees),
            'status': random.choice(statuses),
            'gpa': round(random.uniform(2.0, 4.0), 2)
        }

def create_django_user(first_name, last_name, email=None, is_staff=False):
    """Helper to create Django user"""
    from django.contrib.auth.models import User
    
    username = f"{first_name[0].lower()}{last_name.lower()}"
    email = email or f"{username}@university.edu"
    
    # Check if user exists
    if User.objects.filter(username=username).exists():
        return User.objects.get(username=username)
    
    return User.objects.create_user(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        password='temp123',  # Should be changed by user
        is_staff=is_staff
    )

def populate_database(university_url, num_faculty=10, num_students=50):
    """Main function to populate the database"""
    # 1. Get or generate university data
    scraped_data = scrape_university_website(university_url)
    
    if not scraped_data or not scraped_data['departments']:
        print("Generating dummy departments...")
        scraped_data = {
            'departments': [generate_dummy_data('department') for _ in range(3)],
            'programs': [generate_dummy_data('program') for _ in range(5)],
            'courses': [generate_dummy_data('course') for _ in range(20)]
        }
    
    # 2. Create Departments
    departments = []
    for dept_data in scraped_data['departments']:
        dept, created = Department.objects.get_or_create(
            code=dept_data['code'],
            defaults={
                'name': dept_data['name'],
                'description': dept_data.get('description', ''),
                'location': dept_data.get('location', 'Main Campus'),
                'contact_email': dept_data.get('contact_email', 'contact@university.edu'),
                'website': dept_data.get('website', 'https://university.edu')
            }
        )
        departments.append(dept)
        print(f"Created department: {dept.name}")
    
    # 3. Create Faculty (with Users)
    faculty_members = []
    for _ in range(num_faculty):
        faculty_data = generate_dummy_data('faculty')
        dept = random.choice(departments)
        
        user = create_django_user(
            faculty_data['first_name'],
            faculty_data['last_name'],
            is_staff=True
        )
        
        faculty = Faculty.objects.create(
            user=user,
            department=dept,
            rank=faculty_data['rank'],
            office_location=faculty_data['office_location'],
            phone=faculty_data['phone'],
            hire_date=faculty_data['hire_date'],
            research_interests=faculty_data['research_interests']
        )
        faculty_members.append(faculty)
        print(f"Created faculty: {faculty.user.get_full_name()}")
    
    # Assign department heads
    for dept in departments:
        if not dept.head_of_department:
            dept.head_of_department = random.choice(faculty_members)
            dept.save()
    
    # 4. Create Academic Programs
    programs = []
    for program_data in scraped_data['programs']:
        program = AcademicProgram.objects.create(
            name=program_data['name'],
            code=program_data['code'],
            description=program_data.get('description', ''),
            department=random.choice(departments),
            program_type=program_data.get('program_type', 'MAJ'),
            degree=program_data.get('degree', 'BS'),
            total_credits_required=program_data.get('total_credits_required', 120),
            duration_years=program_data.get('duration_years', 4)
        )
        programs.append(program)
        print(f"Created program: {program.name}")
    
    # 5. Create Courses
    courses = []
    for course_data in scraped_data['courses']:
        course = Course.objects.create(
            code=course_data['code'],
            title=course_data['title'],
            description=course_data['description'],
            department=random.choice(departments),
            credits=course_data['credits'],
            level=course_data['level'],
            is_core=course_data['is_core']
        )
        courses.append(course)
        print(f"Created course: {course.code} - {course.title}")
    
    # 6. Create Program-Course relationships
    for program in programs:
        # Assign 5-10 courses to each program
        program_courses = random.sample(courses, random.randint(5, 10))
        for course in program_courses:
            ProgramCourse.objects.create(
                program=program,
                course=course,
                is_required=random.choice([True, False]),
                semester_offered=random.randint(1, 8)
            )
    
    # 7. Create Students (with Users)
    students = []
    for _ in range(num_students):
        student_data = generate_dummy_data('student')
        
        user = create_django_user(
            student_data['first_name'],
            student_data['last_name']
        )
        
        student = Student.objects.create(
            user=user,
            student_id=student_data['student_id'],
            date_of_birth=student_data['date_of_birth'],
            admission_date=fake.date_between(start_date='-4y', end_date='today'),
            expected_graduation=fake.date_between(start_date='today', end_date='+4y'),
            current_program=random.choice(programs),
            degree_type=student_data['degree_type'],
            status=student_data['status'],
            advisor=random.choice(faculty_members),
            gpa=student_data['gpa']
        )
        students.append(student)
        print(f"Created student: {student.user.get_full_name()}")
    
    # 8. Create Semesters
    semesters = []
    seasons = ['FA', 'SP', 'SU']
    current_year = datetime.now().year
    
    for year in range(current_year - 2, current_year + 1):
        for season in seasons:
            semester = Semester.objects.create(
                name=f"{season} {year}",
                code=f"{year}{season}",
                year=year,
                season=season,
                start_date=fake.date_between(
                    start_date=datetime(year, 1 if season == 'SP' else 8 if season == 'FA' else 5, 1),
                    end_date=datetime(year, 1 if season == 'SP' else 8 if season == 'FA' else 5, 15)
                ),
                end_date=fake.date_between(
                    start_date=datetime(year, 5 if season == 'SP' else 12 if season == 'FA' else 7, 1),
                    end_date=datetime(year, 5 if season == 'SP' else 12 if season == 'FA' else 7, 30)
                ),
                registration_start=fake.date_between(
                    start_date=datetime(year-1 if season == 'FA' else year, 11 if season == 'SP' else 4 if season == 'SU' else 7, 1),
                    end_date=datetime(year-1 if season == 'FA' else year, 11 if season == 'SP' else 4 if season == 'SU' else 7, 15)
                ),
                registration_end=fake.date_between(
                    start_date=datetime(year, 1 if season == 'SP' else 5 if season == 'SU' else 8, 1),
                    end_date=datetime(year, 1 if season == 'SP' else 5 if season == 'SU' else 8, 15)
                ),
                is_current=(year == current_year and season == ('SP' if datetime.now().month < 5 else 'FA'))
            )
            semesters.append(semester)
            print(f"Created semester: {semester.name}")
    
    # 9. Create Course Offerings
    offerings = []
    for semester in semesters[-3:]:  # Only create offerings for recent semesters
        semester_courses = random.sample(courses, random.randint(10, 20))
        for course in semester_courses:
            offering = CourseOffering.objects.create(
                course=course,
                semester=semester,
                instructor=random.choice(faculty_members),
                section=f"{random.choice(['A', 'B', 'C'])}",
                capacity=random.randint(20, 50),
                enrolled=0,
                classroom=f"Building {random.randint(1, 5)}-{random.randint(100, 300)}",
                schedule=random.choice(["MWF 10:00-10:50", "TTH 11:00-12:15", "M 6:00-8:30"])
            )
            offerings.append(offering)
            print(f"Created offering: {offering.course.code} - {offering.section} ({offering.semester})")
    
    # 10. Create Enrollments
    for offering in offerings:
        # Enroll 10-90% of capacity
        num_enrollments = random.randint(
            int(offering.capacity * 0.1),
            int(offering.capacity * 0.9)
        )
        
        offering_students = random.sample(students, num_enrollments)
        offering.enrolled = num_enrollments
        offering.save()
        
        for student in offering_students:
            Enrollment.objects.create(
                student=student,
                course_offering=offering,
                grade=random.choice(['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F', None]),
                status='completed' if offering.semester.end_date < datetime.now().date() else 'registered',
                credits_attempted=offering.course.credits,
                credits_earned=offering.course.credits if random.random() > 0.1 else 0  # 10% chance of failing
            )
        print(f"Created {num_enrollments} enrollments for {offering.course.code}")
    
    # 11. Create Buildings and Rooms
    buildings = []
    for i in range(1, 6):
        building = Building.objects.create(
            name=f"{fake.last_name()} Hall",
            code=f"B{i:02d}",
            location=fake.street_address(),
            description=f"Academic building {i}"
        )
        buildings.append(building)
        
        # Create 5-10 rooms per building
        for j in range(1, random.randint(5, 10)):
            Room.objects.create(
                building=building,
                room_number=f"{i}{j:02d}",
                capacity=random.choice([20, 30, 50, 100, 200]),
                room_type=random.choice(["Classroom", "Lab", "Lecture Hall", "Seminar Room"])
            )
        print(f"Created building {building.name} with rooms")
    
    print("\nDatabase population complete!")

if __name__ == "__main__":
    university_url = "https://www.exampleuniversity.edu"  # Replace with actual university URL
    populate_database(university_url)