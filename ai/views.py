import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import google.generativeai as genai
from django.db.models import Q
from university.models import (
    Department, Faculty, Student, AcademicProgram, 
    Course, ProgramCourse, Semester, CourseOffering,
    Enrollment, Transcript, Announcement, Building, Room
)
from django.contrib.auth.models import User

# Configure Gemini
genai.configure(api_key="AIzaSyDP3DaGFyycm-QxCg5muMgEQmd4CZySlyI")

def parse_gemini_response(response_text):
    """Helper function to safely parse Gemini's JSON response."""
    try:
        # Clean the response text
        cleaned_text = response_text.strip()
        if cleaned_text.startswith('```json'):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.endswith('```'):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()
        
        # Parse the JSON
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        # Fallback to default response if parsing fails
        return {
            "intent": "other",
            "entities": {}
        }

@api_view(['POST'])
def university_assistant(request):
    """
    Comprehensive university assistant endpoint that handles natural language queries
    across all university data models and returns human-like responses.
    """
    user_query = request.data.get('query', '').strip()
    if not user_query:
        return Response({'error': 'Query parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Step 1: Analyze intent and entities
        intent_prompt = f"""
        Analyze this university-related query and respond with ONLY a JSON object containing:
        - "intent" (one of: department_info, faculty_info, student_info, program_info, 
                   course_info, enrollment_info, building_info, announcement, other)
        - "entities" (a dictionary of relevant attributes like department, faculty_name, etc.)
        
        Example response:
        {{
            "intent": "program_info",
            "entities": {{
                "program_type": "graduate",
                "department": "Computer Science"
            }}
        }}
        
        Query to analyze: "{user_query}"
        """
        
        intent_response = model.generate_content(intent_prompt)
        intent_data = parse_gemini_response(intent_response.text)

        # Step 2: Fetch data based on intent
        result_data = []
        response_template = ""
        
        # Department Information
        if intent_data['intent'] == 'department_info':
            depts = Department.objects.all()
            if 'department' in intent_data['entities']:
                depts = depts.filter(
                    Q(name__icontains=intent_data['entities']['department']) |
                    Q(code__icontains=intent_data['entities']['department'])
                )
            
            result_data = [{
                'name': d.name,
                'code': d.code,
                'description': d.description,
                'location': d.location,
                'contact': d.contact_email,
                'website': d.website,
                'head': d.head_of_department.user.get_full_name() if d.head_of_department else None
            } for d in depts]
            
            response_template = "Here's information about the department(s):"

        # Faculty Information
        elif intent_data['intent'] == 'faculty_info':
            faculty = Faculty.objects.select_related('user', 'department').all()
            
            if 'faculty_name' in intent_data['entities']:
                faculty = faculty.filter(
                    Q(user__first_name__icontains=intent_data['entities']['faculty_name']) |
                    Q(user__last_name__icontains=intent_data['entities']['faculty_name'])
                )
            
            if 'department' in intent_data['entities']:
                faculty = faculty.filter(
                    department__name__icontains=intent_data['entities']['department']
                )
            
            result_data = [{
                'name': f.user.get_full_name(),
                'title': f.get_rank_display(),
                'department': f.department.name,
                'office': f.office_location,
                'phone': f.phone,
                'email': f.user.email,
                'research': f.research_interests,
                'office_hours': f.office_hours
            } for f in faculty]
            
            response_template = "Here are faculty members matching your query:"

        # Academic Programs
        elif intent_data['intent'] == 'program_info':
            programs = AcademicProgram.objects.select_related('department').all()
            
            if 'program_type' in intent_data['entities']:
                programs = programs.filter(
                    Q(program_type__icontains=intent_data['entities']['program_type']) |
                    Q(degree__icontains=intent_data['entities']['program_type'])
                )
            
            if 'department' in intent_data['entities']:
                programs = programs.filter(
                    department__name__icontains=intent_data['entities']['department']
                )
            
            result_data = [{
                'name': p.name,
                'type': p.get_program_type_display(),
                'degree': p.get_degree_display(),
                'department': p.department.name,
                'credits': p.total_credits_required,
                'duration': f"{p.duration_years} years",
                'description': p.description
            } for p in programs]
            
            response_template = "Here are academic programs matching your query:"

        # Course Information
        elif intent_data['intent'] == 'course_info':
            courses = Course.objects.select_related('department').all()
            
            if 'course_level' in intent_data['entities']:
                courses = courses.filter(
                    level__icontains=intent_data['entities']['course_level']
                )
            
            if 'department' in intent_data['entities']:
                courses = courses.filter(
                    department__name__icontains=intent_data['entities']['department']
                )
            
            result_data = [{
                'code': c.code,
                'title': c.title,
                'department': c.department.name,
                'level': c.get_level_display(),
                'credits': c.credits,
                'description': c.description,
                'is_core': c.is_core
            } for c in courses]
            
            response_template = "Here are courses matching your query:"

        # Enrollment Information
        elif intent_data['intent'] == 'enrollment_info':
            enrollments = Enrollment.objects.select_related(
                'student__user', 'course_offering__course', 'course_offering__semester'
            ).all()
            
            if 'student' in intent_data['entities']:
                enrollments = enrollments.filter(
                    Q(student__user__first_name__icontains=intent_data['entities']['student']) |
                    Q(student__user__last_name__icontains=intent_data['entities']['student'])
                )
            
            if 'course' in intent_data['entities']:
                enrollments = enrollments.filter(
                    course_offering__course__title__icontains=intent_data['entities']['course']
                )
            
            result_data = [{
                'student': e.student.user.get_full_name(),
                'course': e.course_offering.course.title,
                'semester': str(e.course_offering.semester),
                'grade': e.get_grade_display() if e.grade else None,
                'status': e.status
            } for e in enrollments]
            
            response_template = "Here are enrollment records matching your query:"

        # Building Information
        elif intent_data['intent'] == 'building_info':
            buildings = Building.objects.all()
            
            if 'building' in intent_data['entities']:
                buildings = buildings.filter(
                    Q(name__icontains=intent_data['entities']['building']) |
                    Q(code__icontains=intent_data['entities']['building'])
                )
            
            result_data = [{
                'name': b.name,
                'code': b.code,
                'location': b.location,
                'description': b.description
            } for b in buildings]
            
            response_template = "Here are campus buildings matching your query:"

        # Announcements
        elif intent_data['intent'] == 'announcement':
            announcements = Announcement.objects.select_related('author').all()
            
            if 'urgency' in intent_data['entities']:
                announcements = announcements.filter(is_urgent=True)
            
            result_data = [{
                'title': a.title,
                'content': a.content,
                'author': a.author.get_full_name() if a.author else None,
                'date': a.publish_date.strftime("%Y-%m-%d"),
                'is_urgent': a.is_urgent
            } for a in announcements.order_by('-publish_date')[:5]]
            
            response_template = "Here are recent university announcements:"

        # General University Information
        else:
            result_data = {
                'departments_count': Department.objects.count(),
                'faculty_count': Faculty.objects.count(),
                'programs_count': AcademicProgram.objects.count(),
                'active_students': Student.objects.filter(status='A').count(),
                'current_semester': str(Semester.objects.filter(is_current=True).first())
            }
            response_template = "Here's general information about the university:"

        # Step 3: Generate natural language response
        response_prompt = f"""
        You are a helpful university assistant. The user asked: "{user_query}"
        
        Context: {response_template}
        
        Relevant Data (in JSON format):
        {json.dumps(result_data, indent=2)}
        
        Please generate a concise, friendly response (2-3 paragraphs max) that:
        1. Directly answers the user's question
        2. Includes the most relevant information from the data
        3. Formats the information in a clear, readable way
        4. If no results were found, politely explain this
        
        Respond with just the plain text answer, without any JSON formatting or code blocks.
        """
        
        final_response = model.generate_content(response_prompt)
        
        return Response({
            'query': user_query,
            'intent': intent_data,
            'data': result_data,
            'response': final_response.text
        })

    except Exception as e:
        return Response({
            'error': str(e),
            'message': 'An error occurred processing your request'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)