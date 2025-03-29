from django.db import models

class Professor(models.Model):
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    contact_info = models.CharField(max_length=100)

    def __str__(self):
        return self.name