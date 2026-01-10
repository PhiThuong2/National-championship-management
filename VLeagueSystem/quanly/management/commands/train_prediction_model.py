"""
Django Management Command: Train AI Prediction Model
Usage: python manage.py train_prediction_model [--season SEASON_NAME] [--min-matches 15]
"""
from django.core.management.base import BaseCommand, CommandError
from quanly.models import Season, Match
from quanly.ml.feature_engineering import build_training_dataset
from quanly.ml.prediction_models import EnsemblePredictor


class Command(BaseCommand):
    help = 'Train AI prediction models using historical match data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=str,
            help='Season name to train on (e.g., "V-League 2023"). If not specified, uses all seasons.'
        )
        parser.add_argument(
            '--min-matches',
            type=int,
            default=15,
            help='Minimum number of matches required for training (default: 15, reduced for testing)'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('AI MATCH PREDICTION - MODEL TRAINING'))
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write('')
        
        # Get season
        season = None
        if options['season']:
            try:
                season = Season.objects.get(name__icontains=options['season'])
                self.stdout.write(f"Training on season: {season.name}")
            except Season.DoesNotExist:
                raise CommandError(f"Season '{options['season']}' not found!")
        else:
            self.stdout.write("Training on all available seasons")
        
        min_matches = options['min_matches']
        
        # Check available data
        finished_matches = Match.objects.filter(status='FINISHED')
        if season:
            finished_matches = finished_matches.filter(season=season)
        
        match_count = finished_matches.count()
        self.stdout.write(f"Finished matches available: {match_count}")
        
        if match_count < min_matches:
            self.stdout.write(self.style.ERROR(
                f"\nERROR: Không đủ dữ liệu để training!"
            ))
            self.stdout.write(self.style.ERROR(
                f"Cần ít nhất {min_matches} trận đã hoàn thành, hiện có {match_count} trận."
            ))
            self.stdout.write(self.style.WARNING(
                f"\nGợi ý: Sử dụng lệnh 'python manage.py generate_sample_matches' để tạo dữ liệu mẫu."
            ))
            return
        
        self.stdout.write(self.style.SUCCESS(f"✓ Đủ dữ liệu để training ({match_count} trận)"))
        self.stdout.write('')
        
        # Build training dataset
        self.stdout.write("Building training dataset...")
        try:
            training_data = build_training_dataset(season=season, min_matches=min_matches)
            self.stdout.write(self.style.SUCCESS(f"✓ Dataset created: {len(training_data)} samples"))
        except Exception as e:
            raise CommandError(f"Error building dataset: {str(e)}")
        
        # Train models
        self.stdout.write('')
        self.stdout.write("Training AI models...")
        self.stdout.write('-' * 40)
        
        try:
            predictor = EnsemblePredictor()
            metrics = predictor.train(training_data)
            
            # Display Poisson model metrics
            self.stdout.write('')
            self.stdout.write(self.style.HTTP_INFO('POISSON REGRESSION MODEL:'))
            
            # Note: metrics dictionary structure depends on EnsemblePredictor implementation
            # Adapting to the structure in quanly.ml.prediction_models
            
            poisson = metrics['poisson_metrics']
            self.stdout.write(f"  Home Score Accuracy: {poisson['home_accuracy']:.2%}")
            self.stdout.write(f"  Away Score Accuracy: {poisson['away_accuracy']:.2%}")
            self.stdout.write(f"  Overall Accuracy: {poisson['overall_accuracy']:.2%}")
            
            # Display Random Forest metrics  
            self.stdout.write('')
            self.stdout.write(self.style.HTTP_INFO('RANDOM FOREST CLASSIFIER:'))
            rf = metrics['rf_metrics']
            self.stdout.write(f"  Result Prediction Accuracy: {rf['accuracy']:.2%}")
            
            report = rf['classification_report']
            # classification_report from sklearn returns dict of dicts
            
            self.stdout.write('')
            self.stdout.write("  Classification Details:")
            # Keys might be '1', '0', '-1' or 'Home Win', etc depending on implementation
            # In prediction_models.py, it uses target_names=['Home Win', 'Draw', 'Away Win']
            
            for label, stats in report.items():
                if isinstance(stats, dict): 
                    self.stdout.write(f"    {label}:")
                    self.stdout.write(f"      Precision: {stats['precision']:.2%}")
                    self.stdout.write(f"      Recall: {stats['recall']:.2%}")
            
            # Save models
            self.stdout.write('')
            self.stdout.write("Saving models...")
            saved_paths = predictor.save_models()
            self.stdout.write(self.style.SUCCESS(f"✓ Poisson model saved: {saved_paths['poisson']}"))
            self.stdout.write(self.style.SUCCESS(f"✓ Random Forest model saved: {saved_paths['rf']}"))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise CommandError(f"Error during training: {str(e)}")
        
        # Success summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('TRAINING COMPLETED SUCCESSFULLY!'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f"Training samples: {poisson['training_samples']}")
        self.stdout.write(f"Test samples: {poisson['test_samples']}")
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            "Next step: Run 'python manage.py generate_predictions' to create predictions for upcoming matches."
        ))