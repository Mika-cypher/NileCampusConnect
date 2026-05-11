import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from faker import Faker
from core.models import Category, Service, Wallet

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with dummy users, categories, wallets, and marketplace gigs'

    def handle(self, *args, **kwargs):
        fake = Faker()

        self.stdout.write('Seeding data...')

        # 1. Create Campus Categories
        categories = [
            'Academic Tutoring', 'Graphic Design', 'Programming Help', 
            'Essay Proofreading', 'Campus Errands', 'Photography'
        ]
        cat_objects = {}
        for cat_name in categories:
            cat, created = Category.objects.get_or_create(name=cat_name)
            cat_objects[cat_name] = cat

        # 2. Create Dummy Students (Users & Wallets)
        users = []
        for _ in range(8):  # Creating 8 distinct students
            first_name = fake.first_name()
            last_name = fake.last_name()
            # Add a random number to avoid username collisions
            username = f"{first_name.lower()}_{last_name.lower()}{random.randint(10,99)}"
            email = f"{username}@nileuniversity.edu.ng" 
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'bio': fake.paragraph(nb_sentences=2)
                }
            )

            if created:
                user.set_password('password123')
                user.save()
                # Ensure they have a wallet for your payment system!
                Wallet.objects.get_or_create(user=user)

            users.append(user)

        # 3. Create Dummy Marketplace Gigs (Services)
        # Mapping gigs directly to categories so it looks realistic
        gigs = [
            ("I will tutor you in Data Structures and Algorithms", 'Academic Tutoring'),
            ("I will design an eye-catching flyer for your campus event", 'Graphic Design'),
            ("I will proofread your final year project documentation", 'Essay Proofreading'),
            ("I will take professional headshots for your LinkedIn", 'Photography'),
            ("I will help debug your Python/Django project", 'Programming Help'),
            ("I will pick up your groceries or laundry from town", 'Campus Errands'),
            ("I will write custom Excel macros for your research data", 'Programming Help'),
            ("I will create a custom logo for your student startup", 'Graphic Design'),
            ("I will tutor you in Calculus and Linear Algebra", 'Academic Tutoring'),
            ("I will edit your campus vlog or short film", 'Graphic Design'),
            ("I will wait in line for you at the student affairs office", 'Campus Errands'),
            ("I will review and format your CV for internships", 'Essay Proofreading'),
        ]

        delivery_times = ['1 day', '2 days', '3 days', '1 week']

        for gig_title, cat_name in gigs:
            # Randomly assign a freelancer, price, and delivery time
            freelancer = random.choice(users)
            category = cat_objects[cat_name]
            price = Decimal(random.randint(20, 150) * 100) # Generates prices like 2000.00, 4500.00
            
            Service.objects.create(
                title=gig_title,
                freelancer=freelancer,
                category=category,
                price=price,
                description=fake.paragraph(nb_sentences=5),
                delivery_time=random.choice(delivery_times),
                is_active=True
            )

        self.stdout.write(self.style.SUCCESS('Successfully seeded the marketplace!'))