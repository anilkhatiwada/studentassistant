import json
import re
from datetime import datetime, timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import google.generativeai as genai
from django.db.models import Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.utils import timezone
from django.core.cache import cache
from difflib import SequenceMatcher
from django.contrib.auth.models import User

# Import your models - adjust this import according to your project structure
from university.models import (
    Department, Faculty, Student, AcademicProgram, 
    Course, ProgramCourse, Semester, CourseOffering,
    Enrollment, Transcript, Announcement, Building, Room,
    
)
from .models import KnowledgeBaseEntry

# Configure Gemini
genai.configure(api_key="AIzaSyDP3DaGFyycm-QxCg5muMgEQmd4CZySlyI")

# Context storage duration in seconds (60 minutes)
CONTEXT_DURATION = 3600

def similar(a, b):
    """Calculate text similarity between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def search_knowledge_base(user_query, context=None):
    """
    Enhanced knowledge base search with AI-powered relevance matching
    Features:
    1. Caching for performance
    2. Multiple fallback strategies
    3. Better error handling
    4. Optimized AI prompt
    5. Configurable thresholds
    """
    # Configuration
    MIN_RELEVANCE_SCORE = 40  # Lowered threshold to capture more potential matches
    MAX_RESULTS = 3
    CACHE_TIMEOUT = 3600  # 1 hour cache
    
    # Try cache first if enabled
    cache_key = f"kb_search_{user_query.lower().strip()}"
    cached_results = cache.get(cache_key)
    if cached_results:
        return cached_results
    
    # Strategy 1: Semantic Search (Postgres vector search)
    try:
        vector = SearchVector('question', weight='A') + SearchVector('answer', weight='B')
        query = SearchQuery(user_query)
        
        semantic_results = KnowledgeBaseEntry.objects.annotate(
            search=vector,
            rank=SearchRank(vector, query)
        ).filter(search=query).order_by('-rank')[:MAX_RESULTS*2]  # Get extra for filtering
        
        if semantic_results.exists():
            # Cache and return results
            cache.set(cache_key, list(semantic_results), CACHE_TIMEOUT)
            return semantic_results
    except Exception as e:
        pass  # Silently fall through to next strategy
    
    # Strategy 2: AI-Powered Matching
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Get a representative sample if KB is large
        all_entries = KnowledgeBaseEntry.objects.all()
        if all_entries.count() > 100:
            all_entries = all_entries.order_by('-last_accessed')[:100]  # Get most recently used
        
        # Optimized prompt for better matching
        prompt = f"""
        Analyze this university query and match to knowledge base entries.
        Return JSON with: id (1-based index), relevance_score (0-100), match_reason.
        Only include entries with score >= {MIN_RELEVANCE_SCORE}.
        Prioritize: 1) Direct question matches 2) Answer content 3) Conceptual similarity.
        
        Query: "{user_query}"
        
        Knowledge Base:
        {chr(10).join(f"{i+1}. Q: {e.question[:200]}{'...' if len(e.question)>200 else ''}{chr(10)}A: {e.answer[:200]}{'...' if len(e.answer)>200 else ''}" 
                      for i, e in enumerate(all_entries))}
        """
        
        response = model.generate_content(prompt)
        matches = parse_gemini_response(response.text)
        
        if matches and isinstance(matches, list):
            valid_matches = [m for m in matches if m.get('relevance_score', 0) >= MIN_RELEVANCE_SCORE]
            valid_matches.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            if valid_matches:
                results = []
                for match in valid_matches[:MAX_RESULTS]:
                    try:
                        entry = all_entries[match['id']-1]
                        entry.last_accessed = timezone.now()  # Track usage
                        entry.save()
                        results.append(entry)
                    except IndexError:
                        continue
                
                if results:
                    cache.set(cache_key, results, CACHE_TIMEOUT)
                    return results
    except Exception as e:
        print(f"AI matching error: {e}")  # Consider proper logging
    
    # Strategy 3: Hybrid Fallback Search
    try:
        # Split query into meaningful words
        words = [word for word in re.findall(r'\w+', user_query.lower()) if len(word) > 3]
        
        if words:
            # Create a Q object for each word
            queries = [Q(question__icontains=word) | Q(answer__icontains=word) for word in words]
            
            # Start with the first query
            combined_query = queries.pop()
            
            # OR the remaining queries
            for q in queries:
                combined_query |= q
            
            fallback_results = KnowledgeBaseEntry.objects.filter(combined_query)[:MAX_RESULTS]
            
            if fallback_results.exists():
                cache.set(cache_key, list(fallback_results), CACHE_TIMEOUT)
                return fallback_results
    except Exception as e:
        pass
    
    # Final fallback: Empty result
    return KnowledgeBaseEntry.objects.none()

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

def generate_suggestions(intent_data, result_data):
    """Generate suggested questions based on the intent and results."""
    if not intent_data.get('requires_followup'):
        return None
    
    suggestions = []
    
    if intent_data['intent'] == 'department_info':
        if isinstance(result_data, list) and result_data:
            suggestions = [
                {"name": f"What courses are offered by {dept.get('name', 'this department')}?", "payload": f"courses_{dept.get('code', '')}"}
                for dept in result_data[:2]  # Limit to 2 suggestions
            ]
    
    elif intent_data['intent'] == 'faculty_info':
        if isinstance(result_data, list) and result_data:
            suggestions = [
                {"name": f"What research does {fac.get('name', 'this professor')} specialize in?", "payload": f"research_{fac.get('email', '')}"}
                for fac in result_data[:2]
            ]
    
    elif intent_data['intent'] == 'program_info':
        if isinstance(result_data, list) and result_data:
            suggestions = [
                {"name": f"What are the requirements for {prog.get('name', 'this program')}?", "payload": f"requirements_{prog.get('code', '')}"}
                for prog in result_data[:2]
            ]
    
    if suggestions:
        return {
            "type": "SUGGESTED_QUESTIONS",
            "questions": suggestions
        }
    return None

def format_response_data(intent_data, result_data, text_response):
    """Format the response data according to the frontend interface."""
    response_data = []
    
    # Always include the text response first
    response_data.append({
        "type": "text",
        "content": text_response,
        "meta": None
    })
    
    # Add structured data based on intent
    if intent_data['intent'] == 'program_info' and isinstance(result_data, list):
        for program in result_data[:3]:  # Limit to 3 programs
            response_data.append({
                "type": "article",
                "title": f"{program.get('name', 'Program')} Program",
                "content": program.get('description', ''),
                "link": f"/programs/{program.get('code', '')}",
                "meta": {
                    "degree": program.get('degree', ''),
                    "credits": program.get('credits', '')
                }
            })
    
    elif intent_data['intent'] == 'course_info' and isinstance(result_data, list):
        response_data.append({
            "type": "options",
            "title": "Related Courses",
            "data": [
                {
                    "content": {"code": course.get('code', ''), "name": course.get('title', '')},
                    "type": "course"
                }
                for course in result_data[:5]  # Limit to 5 courses
            ],
            "meta": None
        })
    
    elif intent_data['intent'] == 'faculty_info' and isinstance(result_data, list):
        for faculty in result_data[:3]:
            response_data.append({
                "type": "article",
                "title": f"Professor {faculty.get('name', '')}",
                "content": faculty.get('research', ''),
                "link": f"/faculty/{faculty.get('email', '').split('@')[0] if faculty.get('email') else ''}",
                "meta": {
                    "department": faculty.get('department', ''),
                    "title": faculty.get('title', '')
                }
            })
    
    # Format knowledge base results differently
    elif isinstance(result_data, list) and result_data and isinstance(result_data[0], dict) and 'type' in result_data[0] and result_data[0]['type'] == 'knowledge_base':
        for kb_entry in result_data:
            response_data.append({
                "type": "knowledge_base",
                "title": kb_entry.get('question', '')[:100] + ("..." if len(kb_entry.get('question', '')) > 100 else ""),
                "content": kb_entry.get('answer', ''),
                "source": kb_entry.get('source', 'Troy University Knowledge Base'),
                "meta": {
                    "type": "knowledge_base_result"
                }
            })
    
    return response_data

@api_view(['POST'])
def university_assistant(request):
    """
    University assistant endpoint that returns responses in the format expected by the frontend.
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
        Analyze this university-related query and respond with ONLY a JSON object containing:
        - "intent" (one of: department_info, faculty_info, student_info, program_info, 
                   course_info, enrollment_info, building_info, room_info, announcement, other)
        - "entities" (a dictionary of relevant attributes)
        - "requires_followup" (boolean indicating if follow-up questions might be needed)
        
        Query: "{user_query}"
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


        # Check knowledge base if no primary results found
        if not result_data:
            knowledge_results = search_knowledge_base(user_query, context)
            if knowledge_results:
                result_data = [{
                    'question': kb.question,
                    'answer': kb.answer,
                    'source': kb.source or "Troy University Knowledge Base",
                    'type': 'knowledge_base'
                } for kb in knowledge_results]
                response_template = "Here's some information that might help:"
        
        # If still no results, prepare a generic response
        if not result_data:
            result_data = {
                'message': "I couldn't find specific information about your query.",
                'suggestion': "You might want to contact the university directly or visit troy.edu for more information."
            }
            response_template = "I couldn't find specific information, but here are some general options:"
        
        # Step 3: Generate final response
        response_prompt = f"""
You are a helpful assistant for Troy University in Alabama. The user asked: "{user_query}"

Context: {response_template}

Relevant Data (in JSON format):
{json.dumps(result_data, indent=2)}

Please generate a concise, friendly response that:
1. First try to directly answer the user's question using the provided data
2. If showing knowledge base results, indicate they're from our knowledge base
3. For Troy University-specific information, focus on key aspects when relevant
4. When appropriate, include that you're "Troy University's AI assistant"
5. If appropriate, suggest contacting specific offices or visiting troy.edu
6. Keep the response under 3-4 sentences if possible

Respond with just the plain text answer.
        """
        
        final_response = model.generate_content(response_prompt)
        
        # Generate suggestions for follow-up questions
        suggestions = generate_suggestions(intent_data, result_data)
        
        # Format the response data according to frontend requirements
        formatted_data = format_response_data(intent_data, result_data, final_response.text)
        
        # Update conversation history
        context['conversation_history'].append({
            'timestamp': datetime.now().isoformat(),
            'query': user_query,
            'response': final_response.text,
            'intent': intent_data
        })
        update_user_context(ip_address, context)

        # Prepare the response in the exact format expected by frontend
        response = {
            "query": user_query,
            "data": formatted_data,
            "id": f"res_{datetime.now().timestamp()}",
            "suggestions": [suggestions] if suggestions else None
        }

        return Response(response, status=status.HTTP_200_OK)

    except Exception as e:
        # Return error in the expected format
        error_response = {
            "query": user_query,
            "data": [{
                "type": "text",
                "content": f"Sorry, an error occurred while processing your request: {str(e)}",
                "meta": None
            }],
            "id": "error_response",
            "suggestions": None
        }
        return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)