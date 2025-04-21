# models.py
from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

class KnowledgeBaseEntry(models.Model):
    question = models.TextField()
    answer = models.TextField()
    source = models.URLField(max_length=1000, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: Add this if you want better search capabilities
    search_terms = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.question[:100]
    
    def save(self, *args, **kwargs):
        # Auto-generate search terms if not provided
        if not hasattr(self, 'search_terms') or not self.search_terms:
            super().save(*args, **kwargs)