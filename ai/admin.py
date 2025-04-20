from django.contrib import admin
from .models import KnowledgeBaseEntry

@admin.register(KnowledgeBaseEntry)
class KnowledgeBaseEntryAdmin(admin.ModelAdmin):
    list_display = ('question', 'answer', 'source', 'created_at')
    search_fields = ('question', 'answer')
    list_filter = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 20