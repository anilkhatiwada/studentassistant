from django.db import models
from professor.models import Professor

class Course(models.Model):
    course_name = models.CharField(max_length=100)
    course_description = models.TextField()
    course_schedule = models.CharField(max_length=100)
    professor = models.ForeignKey(Professor, on_delete=models.CASCADE)

    def __str__(self):
        return self.course_name