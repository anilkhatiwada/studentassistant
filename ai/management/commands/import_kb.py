import csv
from django.core.management.base import BaseCommand
from ai.models import KnowledgeBaseEntry

class Command(BaseCommand):
    help = 'Import knowledge base entries from a CSV file'

    def handle(self, *args, **kwargs):
        file_path = 'ai/data/university_knowledge_base.csv'  # Adjust if needed

        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                count = 0
                for i, row in enumerate(reader, 1):
                    question = row.get('question', '').strip()
                    answer = row.get('answer', '').strip()
                    source = row.get('source', '').strip()

                    if not question or not answer:
                        self.stdout.write(f'Skipping row {i}: Missing question or answer')
                        continue

                    KnowledgeBaseEntry.objects.create(
                        question=question,
                        answer=answer,
                        source=source
                    )
                    count += 1

            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} entries.'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))
