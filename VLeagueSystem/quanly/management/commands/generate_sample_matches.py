"""
Django Management Command: Generate Sample Match Data for Testing
Usage: python manage.py generate_sample_matches --count 30
"""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from quanly.models import Match, Team, Season, MatchEvent, MatchEventType


class Command(BaseCommand):
    help = 'Generate sample finished matches for testing AI prediction'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=30,
            help='Number of sample matches to generate (default: 30)'
        )
        parser.add_argument(
            '--season',
            type=str,
            help='Season name to add matches to'
        )
    
    def handle(self, *args, **options):
        count = options['count']
        
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('SAMPLE MATCH DATA GENERATION'))
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write('')
        
        # Get or create season
        if options['season']:
            season = Season.objects.filter(name__icontains=options['season']).first()
            if not season:
                self.stdout.write(self.style.ERROR(f"Season '{options['season']}' not found"))
                return
        else:
            season = Season.objects.filter(is_active=True).first()
            if not season:
                season = Season.objects.order_by('-start_date').first()
        
        if not season:
            self.stdout.write(self.style.ERROR("No season found! Please create a season first."))
            return
        
        self.stdout.write(f"Season: {season.name}")
        
        # Get teams
        teams = list(Team.objects.all())
        if len(teams) < 2:
            self.stdout.write(self.style.ERROR("Need at least 2 teams! Please add teams first."))
            return
        
        self.stdout.write(f"Teams available: {len(teams)}")
        self.stdout.write('')
        
        # Generate matches
        self.stdout.write(f"Generating {count} sample matches...")
        created = 0
        
        base_date = timezone.now() - timedelta(days=count * 3)
        
        for i in range(count):
            # Random teams
            home_team, away_team = random.sample(teams, 2)
            
            # Random score (realistic distribution)
            home_score = random.choices(
                [0, 1, 2, 3, 4],
                weights=[10, 30, 35, 20, 5]
            )[0]
            away_score = random.choices(
                [0, 1, 2, 3, 4],
                weights=[15, 35, 30, 15, 5]
            )[0]
            
            # Match date
            match_date = base_date + timedelta(days=i * 3)
            
            # Create match
            match = Match.objects.create(
                season=season,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                match_date=match_date,
                round_number=(i // (len(teams) // 2)) + 1,
                status='FINISHED'
            )
            
            # Add some random match events
            total_goals = home_score + away_score
            if total_goals > 0:
                for _ in range(total_goals):
                    team = home_team if random.random() > 0.5 else away_team
                    MatchEvent.objects.create(
                        match=match,
                        team=team,
                        event_type=MatchEventType.GOAL,
                        minute=random.randint(1, 90)
                    )
            
            # Add random cards
            num_yellow = random.choices([0, 1, 2, 3], weights=[40, 35, 20, 5])[0]
            for _ in range(num_yellow):
                team = home_team if random.random() > 0.5 else away_team
                MatchEvent.objects.create(
                    match=match,
                    team=team,
                    event_type=MatchEventType.YELLOW_CARD,
                    minute=random.randint(1, 90)
                )
            
            created += 1
            if created % 10 == 0:
                self.stdout.write(f"  Created {created} matches...")
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS(f'CREATED {created} SAMPLE MATCHES'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            "Next step: Run 'python manage.py train_prediction_model' to train the AI models."
        ))
