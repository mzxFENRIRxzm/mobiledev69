from django.db import models

# Create your models here.
class Booking(models.Model):
    # id = models.AutoField(primary_key=True)
    destination_name = models.CharField(max_length=100, default="UBU")
    start_date = models.DateField(default=None, blank=True, null=True)
    end_date = models.DateField(default=None, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} - {self.date} {self.time}"