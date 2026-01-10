"""
Django Management Command: AI Schedule Generation
Usage: python manage.py generate_ai_schedule --season "V-League 2024"
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from quanly.models import Season, Match
from quanly.ml.schedule_generator import (
    AIScheduleGenerator,
    FeasibilityChecker,
    get_schedule_config_from_settings
)


class Command(BaseCommand):
    help = 'Generate AI-optimized match schedule for a season'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=str,
            required=True,
            help='Season name or ID'
        )
        parser.add_argument(
            '--save',
            action='store_true',
            help='Actually save to database (default: preview only)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing matches before generating'
        )
    
    def handle(self, *args, **options):
        season_input = options['season']
        should_save = options['save']
        should_clear = options['clear']
        
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('AI SCHEDULE GENERATION'))
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write('')
        
        # Find season
        try:
            # Try by ID first
            season = Season.objects.get(id=season_input)
        except:
            # Try by name
            season = Season.objects.filter(name__icontains=season_input).first()
        
        if not season:
            self.stdout.write(self.style.ERROR(f"❌ Season '{season_input}' not found"))
            return
        
        self.stdout.write(f"📅 Season: {season.name}")
        self.stdout.write(f"   Start: {season.start_date}")
        self.stdout.write(f"   End: {season.end_date}")
        self.stdout.write('')
        
        # Load configuration
        config = get_schedule_config_from_settings()
        self.stdout.write(f"⚙️  Configuration:")
        self.stdout.write(f"   Valid time slots: {config.valid_time_slots}")
        self.stdout.write(f"   Min rest days: {config.min_rest_days}")
        self.stdout.write(f"   Max rest days: {config.max_rest_days}")
        self.stdout.write(f"   Legs: {config.legs}")
        self.stdout.write('')
        
        # Step 1: Feasibility check
        self.stdout.write(self.style.WARNING("Step 1: Checking feasibility..."))
        checker = FeasibilityChecker(season, config)
        is_feasible, message = checker.check()
        
        if not is_feasible:
            self.stdout.write(self.style.ERROR(f"❌ {message}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"✅ {message}"))
        self.stdout.write('')
        
        # Step 2: Generate schedule
        self.stdout.write(self.style.WARNING("Step 2: Generating AI schedule..."))
        self.stdout.write("   This may take up to 60 seconds...")
        
        generator = AIScheduleGenerator(season, config)
        success, matches_data, gen_message = generator.generate()
        
        if not success:
            self.stdout.write(self.style.ERROR(f"❌ {gen_message}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"✅ {gen_message}"))
        self.stdout.write('')
        
        # Step 3: Display preview
        self.stdout.write(self.style.WARNING("Step 3: Schedule preview"))
        self.stdout.write(f"   Total matches: {len(matches_data)}")
        
        # Group by round
        rounds = {}
        for match in matches_data:
            r = match['round_number']
            if r not in rounds:
                rounds[r] = []
            rounds[r].append(match)
        
        self.stdout.write(f"   Total rounds: {len(rounds)}")
        self.stdout.write('')
        
        # Show first 3 rounds as sample
        for round_num in sorted(rounds.keys())[:3]:
            self.stdout.write(f"   Round {round_num}:")
            for match in rounds[round_num]:
                self.stdout.write(
                    f"      {match['match_date'].strftime('%Y-%m-%d %H:%M')} - "
                    f"{match['home_team'].name} vs {match['away_team'].name}"
                )
        
        if len(rounds) > 3:
            self.stdout.write(f"   ... and {len(rounds) - 3} more rounds")
        
        self.stdout.write('')
        
        # Step 4: Save if requested
        if should_save:
            self.stdout.write(self.style.WARNING("Step 4: Saving to database..."))
            
            with transaction.atomic():
                # Clear existing matches if requested
                if should_clear:
                    deleted, _ = Match.objects.filter(season=season).delete()
                    self.stdout.write(f"   Deleted {deleted} existing matches")
                
                # Create new matches
                created_matches = []
                for match_data in matches_data:
                    match = Match.objects.create(**match_data)
                    created_matches.append(match)
                
                self.stdout.write(self.style.SUCCESS(f"   ✅ Created {len(created_matches)} matches"))
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS(f'SCHEDULE SAVED TO DATABASE'))
            self.stdout.write(self.style.SUCCESS('=' * 70))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('=' * 70))
            self.stdout.write(self.style.WARNING('PREVIEW ONLY - NOT SAVED'))
            self.stdout.write(self.style.WARNING('Use --save flag to save to database'))
            self.stdout.write(self.style.WARNING('Use --clear flag to delete existing matches first'))
            self.stdout.write(self.style.WARNING('=' * 70))
