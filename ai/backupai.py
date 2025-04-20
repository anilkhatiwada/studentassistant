import json
from datetime import datetime, timedelta
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
from django.core.cache import cache

# Configure Gemini
genai.configure(api_key="AIzaSyDP3DaGFyycm-QxCg5muMgEQmd4CZySlyI")

# Context storage duration in seconds (60 minutes)
CONTEXT_DURATION = 3600

def get_client_ip(request):
    """Get the client's IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_user_context(ip_address):
    """Retrieve or create context for a user identified by IP address."""
    context = cache.get(f'university_assistant_context_{ip_address}')
    if not context:
        context = {
            'created_at': datetime.now().isoformat(),
            'conversation_history': [],
            'user_data': {}
        }
        cache.set(f'university_assistant_context_{ip_address}', context, CONTEXT_DURATION)
    return context

def update_user_context(ip_address, context):
    """Update the user's context in cache."""
    cache.set(f'university_assistant_context_{ip_address}', context, CONTEXT_DURATION)

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
            "entities": {},
            "requires_followup": False
        }

@api_view(['POST'])
def university_assistant(request):
    """
    Comprehensive university assistant endpoint that handles natural language queries
    across all university data models and returns human-like responses with context.
    """
    user_query = request.data.get('query', '').strip()
    if not user_query:
        return Response({'error': 'Query parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get or create user context based on IP address
        ip_address = get_client_ip(request)
        context = get_user_context(ip_address)
        
        # Prepare conversation history for context
        conversation_history = "\n".join(
            [f"User: {item['query']}\nAssistant: {item['response']}" 
             for item in context['conversation_history'][-3:]]  # Keep last 3 exchanges
        )
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Step 1: Analyze intent and entities with context
        intent_prompt = f"""
        Previous conversation context (for reference only):
        {conversation_history}
        
        Analyze this new university-related query and respond with ONLY a JSON object containing:
        - "intent" (one of: department_info, faculty_info, student_info, program_info, 
                   course_info, enrollment_info, building_info, room_info, announcement, other)
        - "entities" (a dictionary of relevant attributes including fields from database tables)
        - "requires_followup" (boolean indicating if this question seems to need follow-up questions)
        
        Query to analyze: "{user_query}"
        """
        
        intent_response = model.generate_content(intent_prompt)
        intent_data = parse_gemini_response(intent_response.text)
        
        # Store any entities that might be useful for future context
        if 'entities' in intent_data:
            for key, value in intent_data['entities'].items():
                if value and value not in context['user_data'].values():
                    context['user_data'][key] = value
        
        # Step 2: Fetch data based on intent
        result_data = []
        response_template = ""
        
        # Department Information
        if intent_data['intent'] == 'department_info':
            depts = Department.objects.all()
            if 'department' in intent_data['entities']:
                dept_query = intent_data['entities']['department']
                depts = depts.filter(
                    Q(name__icontains=dept_query) |
                    Q(code__icontains=dept_query) |
                    Q(description__icontains=dept_query) |
                    Q(location__icontains=dept_query)
                )
            
            if 'head_of_department' in intent_data['entities']:
                depts = depts.filter(
                    Q(head_of_department__user__first_name__icontains=intent_data['entities']['head_of_department']) |
                    Q(head_of_department__user__last_name__icontains=intent_data['entities']['head_of_department'])
                )
            
            result_data = [{
                'name': d.name,
                'code': d.code,
                'description': d.description,
                'location': d.location,
                'contact': d.contact_email,
                'website': d.website,
                'head': d.head_of_department.user.get_full_name() if d.head_of_department else None,
                'established_date': d.established_date.strftime("%Y-%m-%d") if d.established_date else None
            } for d in depts]
            
            response_template = "Here's information about the department(s):"

        # Faculty Information
        elif intent_data['intent'] == 'faculty_info':
            faculty = Faculty.objects.select_related('user', 'department').all()
            
            if 'faculty_name' in intent_data['entities']:
                name_query = intent_data['entities']['faculty_name']
                faculty = faculty.filter(
                    Q(user__first_name__icontains=name_query) |
                    Q(user__last_name__icontains=name_query) |
                    Q(user__username__icontains=name_query)
                )
            
            if 'department' in intent_data['entities']:
                faculty = faculty.filter(
                    Q(department__name__icontains=intent_data['entities']['department']) |
                    Q(department__code__icontains=intent_data['entities']['department'])
                )
            
            if 'rank' in intent_data['entities']:
                faculty = faculty.filter(
                    rank__icontains=intent_data['entities']['rank']
                )
            
            if 'research' in intent_data['entities']:
                faculty = faculty.filter(
                    research_interests__icontains=intent_data['entities']['research']
                )
            
            result_data = [{
                'name': f.user.get_full_name(),
                'title': f.get_rank_display(),
                'department': f.department.name,
                'office': f.office_location,
                'phone': f.phone,
                'email': f.user.email,
                'research': f.research_interests,
                'office_hours': f.office_hours,
                'hire_date': f.hire_date.strftime("%Y-%m-%d") if f.hire_date else None
            } for f in faculty]
            
            response_template = "Here are faculty members matching your query:"

        # Student Information
        elif intent_data['intent'] == 'student_info':
            students = Student.objects.select_related('user', 'current_program').all()
            
            if 'student_name' in intent_data['entities']:
                name_query = intent_data['entities']['student_name']
                students = students.filter(
                    Q(user__first_name__icontains=name_query) |
                    Q(user__last_name__icontains=name_query) |
                    Q(user__username__icontains=name_query)
                )
            
            if 'student_id' in intent_data['entities']:
                students = students.filter(
                    student_id__icontains=intent_data['entities']['student_id']
                )
            
            if 'status' in intent_data['entities']:
                students = students.filter(
                    status__icontains=intent_data['entities']['status']
                )
            
            if 'gpa' in intent_data['entities']:
                try:
                    gpa_value = float(intent_data['entities']['gpa'])
                    students = students.filter(gpa__gte=gpa_value-0.2, gpa__lte=gpa_value+0.2)
                except ValueError:
                    pass
            
            if 'program' in intent_data['entities']:
                students = students.filter(
                    Q(current_program__name__icontains=intent_data['entities']['program']) |
                    Q(current_program__code__icontains=intent_data['entities']['program'])
                )
            
            result_data = [{
                'name': s.user.get_full_name(),
                'student_id': s.student_id,
                'email': s.user.email,
                'program': s.current_program.name if s.current_program else None,
                'status': s.get_status_display(),
                'gpa': s.gpa,
                'advisor': s.advisor.user.get_full_name() if s.advisor else None,
                'admission_date': s.admission_date.strftime("%Y-%m-%d") if s.admission_date else None,
                'expected_graduation': s.expected_graduation.strftime("%Y-%m-%d") if s.expected_graduation else None
            } for s in students]
            
            response_template = "Here are students matching your query:"

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
                    Q(department__name__icontains=intent_data['entities']['department']) |
                    Q(department__code__icontains=intent_data['entities']['department'])
                )
            
            if 'degree' in intent_data['entities']:
                programs = programs.filter(
                    degree__icontains=intent_data['entities']['degree']
                )
            
            if 'credits' in intent_data['entities']:
                try:
                    credits = int(intent_data['entities']['credits'])
                    programs = programs.filter(total_credits_required=credits)
                except ValueError:
                    pass
            
            result_data = [{
                'name': p.name,
                'type': p.get_program_type_display(),
                'degree': p.get_degree_display(),
                'department': p.department.name,
                'credits': p.total_credits_required,
                'duration': f"{p.duration_years} years",
                'description': p.description,
                'code': p.code
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
                    Q(department__name__icontains=intent_data['entities']['department']) |
                    Q(department__code__icontains=intent_data['entities']['department'])
                )
            
            if 'course_code' in intent_data['entities']:
                courses = courses.filter(
                    code__icontains=intent_data['entities']['course_code']
                )
            
            if 'course_title' in intent_data['entities']:
                courses = courses.filter(
                    title__icontains=intent_data['entities']['course_title']
                )
            
            if 'credits' in intent_data['entities']:
                try:
                    credits = int(intent_data['entities']['credits'])
                    courses = courses.filter(credits=credits)
                except ValueError:
                    pass
            
            result_data = [{
                'code': c.code,
                'title': c.title,
                'department': c.department.name,
                'level': c.get_level_display(),
                'credits': c.credits,
                'description': c.description,
                'is_core': c.is_core,
                'prerequisites': [p.code for p in c.prerequisites.all()]
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
                    Q(student__user__last_name__icontains=intent_data['entities']['student']) |
                    Q(student__student_id__icontains=intent_data['entities']['student'])
                )
            
            if 'course' in intent_data['entities']:
                enrollments = enrollments.filter(
                    Q(course_offering__course__title__icontains=intent_data['entities']['course']) |
                    Q(course_offering__course__code__icontains=intent_data['entities']['course'])
                )
            
            if 'semester' in intent_data['entities']:
                enrollments = enrollments.filter(
                    Q(course_offering__semester__name__icontains=intent_data['entities']['semester']) |
                    Q(course_offering__semester__code__icontains=intent_data['entities']['semester'])
                )
            
            if 'grade' in intent_data['entities']:
                enrollments = enrollments.filter(
                    grade__icontains=intent_data['entities']['grade']
                )
            
            result_data = [{
                'student': e.student.user.get_full_name(),
                'student_id': e.student.student_id,
                'course': e.course_offering.course.title,
                'course_code': e.course_offering.course.code,
                'semester': str(e.course_offering.semester),
                'grade': e.get_grade_display() if e.grade else None,
                'status': e.status,
                'enrollment_date': e.enrollment_date.strftime("%Y-%m-%d") if e.enrollment_date else None
            } for e in enrollments]
            
            response_template = "Here are enrollment records matching your query:"

        # Building Information
        elif intent_data['intent'] == 'building_info':
            buildings = Building.objects.all()
            
            if 'building' in intent_data['entities']:
                buildings = buildings.filter(
                    Q(name__icontains=intent_data['entities']['building']) |
                    Q(code__icontains=intent_data['entities']['building']) |
                    Q(location__icontains=intent_data['entities']['building'])
                )
            
            result_data = [{
                'name': b.name,
                'code': b.code,
                'location': b.location,
                'description': b.description
            } for b in buildings]
            
            response_template = "Here are campus buildings matching your query:"

        # Room Information
        elif intent_data['intent'] == 'room_info':
            rooms = Room.objects.select_related('building').all()
            
            if 'room' in intent_data['entities']:
                rooms = rooms.filter(
                    Q(room_number__icontains=intent_data['entities']['room']) |
                    Q(building__name__icontains=intent_data['entities']['room']) |
                    Q(building__code__icontains=intent_data['entities']['room'])
                )
            
            if 'room_type' in intent_data['entities']:
                rooms = rooms.filter(
                    room_type__icontains=intent_data['entities']['room_type']
                )
            
            if 'capacity' in intent_data['entities']:
                try:
                    capacity = int(intent_data['entities']['capacity'])
                    rooms = rooms.filter(capacity__gte=capacity-5, capacity__lte=capacity+5)
                except ValueError:
                    pass
            
            result_data = [{
                'building': b.building.name,
                'building_code': b.building.code,
                'room_number': b.room_number,
                'type': b.room_type,
                'capacity': b.capacity,
                'features': b.features
            } for b in rooms]
            
            response_template = "Here are rooms matching your query:"

        # Announcements
        elif intent_data['intent'] == 'announcement':
            announcements = Announcement.objects.select_related('author').all()
            
            if 'urgency' in intent_data['entities']:
                announcements = announcements.filter(is_urgent=True)
            
            if 'announcement_title' in intent_data['entities']:
                announcements = announcements.filter(
                    title__icontains=intent_data['entities']['announcement_title']
                )
            
            if 'target' in intent_data['entities']:
                announcements = announcements.filter(
                    target_audience__icontains=intent_data['entities']['target']
                )
            
            result_data = [{
                'title': a.title,
                'content': a.content,
                'author': a.author.get_full_name() if a.author else None,
                'date': a.publish_date.strftime("%Y-%m-%d"),
                'is_urgent': a.is_urgent,
                'target': a.get_target_audience_display()
            } for a in announcements.order_by('-publish_date')[:5]]
            
            response_template = "Here are recent university announcements:"

        # General University Information
        else:
            result_data = {
                'departments_count': Department.objects.count(),
                'faculty_count': Faculty.objects.count(),
                'programs_count': AcademicProgram.objects.count(),
                'active_students': Student.objects.filter(status='A').count(),
                'current_semester': str(Semester.objects.filter(is_current=True).first()),
                'total_courses': Course.objects.count(),
                'total_buildings': Building.objects.count()
            }
            response_template = "Here's general information about the university:"

        # Step 3: Generate natural language response with context
        response_prompt = f"""
        Conversation history for context:
        {conversation_history}
        
        You are a helpful university assistant. The user asked: "{user_query}"
        
        Context: {response_template}
        
        Relevant Data (in JSON format):
        {json.dumps(result_data, indent=2)}
        
        Additional user context that might be relevant:
        {json.dumps(context['user_data'], indent=2)}
        
        Please generate a concise, friendly response that:
        1. Directly answers the user's question
        2. References previous context if relevant
        3. Includes the most relevant information from the data
        4. Formats the information clearly
        5. If no results were found, politely explain this
        6. For tabular data, present it in a structured format
        7. If the intent suggests a follow-up might be needed, prompt the user appropriately
        
        Respond with just the plain text answer, without any JSON formatting or code blocks.
        """
        
        final_response = model.generate_content(response_prompt)
        
        # Update conversation history
        context['conversation_history'].append({
            'timestamp': datetime.now().isoformat(),
            'query': user_query,
            'response': final_response.text,
            'intent': intent_data
        })
        update_user_context(ip_address, context)

        context = {
            
             "query": user_query,
             "data": [
           {
        "type": "text",
        "content":final_response.text,
        "meta": "",
      }]
        }

        return Response(context, status=status.HTTP_200_OK)
        # Uncomment the following lines to return the full response
        
        # return Response({
        #     'query': user_query,
        #     'intent': intent_data,
        #     'data': result_data,
        #     'response': final_response.text,
        #     'session_id': ip_address  # Return the session identifier to the client
        # })

    except Exception as e:
        return Response({
            'error': str(e),
            'message': 'An error occurred processing your request'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)