"""
Django Management Command: Generate AI Predictions for Upcoming Matches
Usage: python manage.py generate_ai_predictions [--round ROUND_NUM]
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from quanly.models import Match, AIPrediction, Season
from quanly.ml.prediction_models import EnsemblePredictor


class Command(BaseCommand):
    help = 'Generate AI predictions for scheduled matches'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--round',
            type=int,
            help='Specific round number to generate predictions for'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate predictions even if they already exist'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('AI PREDICTION GENERATION'))
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write('')
        
        # Load trained models
        self.stdout.write("Loading trained models...")
        try:
            predictor = EnsemblePredictor()
            predictor.load_models()
            self.stdout.write(self.style.SUCCESS("✓ Models loaded successfully"))
        except FileNotFoundError:
            raise CommandError(
                "Trained models not found! Please run 'python manage.py train_prediction_model' first."
            )
        except Exception as e:
            raise CommandError(f"Error loading models: {str(e)}")
        
        # Get scheduled matches
        matches_query = Match.objects.filter(status='SCHEDULED').select_related(
            'home_team', 'away_team', 'season'
        ).order_by('match_date')
        
        if options['round']:
            matches_query = matches_query.filter(round_number=options['round'])
            self.stdout.write(f"Filtering for round {options['round']}")
        
        matches = list(matches_query)
        
        if not matches:
            self.stdout.write(self.style.WARNING("No scheduled matches found."))
            return
        
        self.stdout.write(f"Found {len(matches)} scheduled matches")
        self.stdout.write('')
        
        # Generate predictions
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for match in matches:
            # Check if prediction already exists
            existing = AIPrediction.objects.filter(match=match).first()
            
            if existing and not options['force']:
                skipped_count += 1
                continue
            
            try:
                # Generate prediction
                prediction = predictor.predict(
                    match.home_team,
                    match.away_team,
                    match.match_date,
                    match.season
                )
                
                # Save to database
                if existing:
                    # Update existing
                    existing.predicted_home_score = prediction['predicted_home_score']
                    existing.predicted_away_score = prediction['predicted_away_score']
                    existing.win_probability = prediction['win_probability']
                    existing.draw_probability = prediction['draw_probability']
                    existing.loss_probability = prediction['loss_probability']
                    existing.confidence_score = prediction['confidence_score']
                    existing.model_version = prediction['model_version']
                    existing.save()
                    updated_count += 1
                    action = "Updated"
                else:
                    # Create new
                    AIPrediction.objects.create(
                        match=match,
                        predicted_home_score=prediction['predicted_home_score'],
                        predicted_away_score=prediction['predicted_away_score'],
                        win_probability=prediction['win_probability'],
                        draw_probability=prediction['draw_probability'],
                        loss_probability=prediction['loss_probability'],
                        confidence_score=prediction['confidence_score'],
                        model_version=prediction['model_version']
                    )
                    created_count += 1
                    action = "Created"
                
                # Display prediction
                self.stdout.write(
                    f"{action}: {match.home_team.name} vs {match.away_team.name} - "
                    f"Dự đoán: {prediction['predicted_home_score']}-{prediction['predicted_away_score']} "
                    f"(Confidence: {prediction['confidence_score']:.1%})"
                )
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Error predicting {match}: {str(e)}"
                ))
                continue
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('PREDICTION GENERATION COMPLETED'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Updated: {updated_count}")
        self.stdout.write(f"Skipped: {skipped_count}")
        self.stdout.write(f"Total processed: {created_count + updated_count + skipped_count}")
