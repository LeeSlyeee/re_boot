from django.db import models

class CourseSection(models.Model):
    title = models.CharField(max_length=200)
    day_sequence = models.IntegerField(help_text="1일차, 2일차...")
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['day_sequence']

    def __str__(self):
        return f"Day {self.day_sequence}: {self.title}"
