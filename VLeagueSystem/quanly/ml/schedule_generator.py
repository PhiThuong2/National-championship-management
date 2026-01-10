"""
AI-Powered Schedule Generator for V-League
Uses constraint optimization (Google OR-Tools) to generate tournament schedules
"""
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from ortools.sat.python import cp_model
from django.db.models import Q
from django.utils import timezone

from quanly.models import Season, Team, Match, SystemSetting


@dataclass
class ScheduleConfig:
    """Configuration for schedule generation"""
    valid_time_slots: List[Tuple[int, int]]  # List of (hour, minute) tuples
    min_rest_days: int = 5
    max_rest_days: int = 7
    prefer_weekends: bool = True
    legs: int = 2  # Number of home/away legs


class FeasibilityChecker:
    """Checks if a season is feasible for schedule generation"""
    
    def __init__(self, season: Season, config: ScheduleConfig):
        self.season = season
        self.config = config
        self.teams = list(Team.objects.all())
        
    def check(self) -> Tuple[bool, str]:
        """
        Check if schedule generation is feasible
        
        Returns:
            (is_feasible, error_message)
        """
        # Check 1: Enough teams
        if len(self.teams) < 2:
            return False, "Cần ít nhất 2 đội bóng để tạo lịch thi đấu"
        
        # Check 2: Calculate required days
        num_teams = len(self.teams)
        if num_teams % 2 == 1:
            num_teams += 1  # Add bye team
        
        # Each round has num_teams/2 matches
        # Total rounds = (num_teams - 1) * legs
        rounds_per_leg = num_teams - 1
        total_rounds = rounds_per_leg * self.config.legs
        
        # Calculate minimum required days
        # Each round needs at least 2 days (Saturday + Sunday)
        # Plus minimum rest days between rounds
        min_required_days = (total_rounds * 2) + ((total_rounds - 1) * self.config.min_rest_days)
        
        # Check 3: Season duration
        season_duration = (self.season.end_date - self.season.start_date).days
        
        if season_duration < min_required_days:
            return False, (
                f"Mùa giải quá ngắn!\n"
                f"- Số đội: {len(self.teams)}\n"
                f"- Số vòng đấu: {total_rounds}\n"
                f"- Thời gian cần thiết: tối thiểu {min_required_days} ngày\n"
                f"- Thời gian thực tế: {season_duration} ngày\n"
                f"Vui lòng kéo dài mùa giải hoặc giảm số vòng đấu"
            )
        
        # Check 4: Valid time slots exist
        if not self.config.valid_time_slots:
            return False, "Không có khung giờ thi đấu hợp lệ được cấu hình"
        
        return True, f"Khả thi! Có thể tạo lịch {total_rounds} vòng đấu trong {season_duration} ngày"


class AIScheduleGenerator:
    """
    AI-powered schedule generator using constraint programming
    """
    
    def __init__(self, season: Season, config: ScheduleConfig):
        self.season = season
        self.config = config
        self.teams = list(Team.objects.all().order_by('name'))
        self.num_teams = len(self.teams)
        
        # Handle odd number of teams by adding a "bye"
        self.has_bye = self.num_teams % 2 != 0
        if self.has_bye:
            self.num_teams_adjusted = self.num_teams + 1
        else:
            self.num_teams_adjusted = self.num_teams
        
        self.rounds_per_leg = self.num_teams_adjusted - 1
        self.total_rounds = self.rounds_per_leg * self.config.legs
        
        # Model and variables
        self.model = cp_model.CpModel()
        self.matches = {}  # (round, home_team, away_team) -> var
        self.match_dates = {}  # (round, home_team, away_team) -> date_var
        self.match_times = {}  # (round, home_team, away_team) -> time_slot_var
        
    def _get_available_dates(self) -> List[datetime.date]:
        """Generate list of possible match dates (weekends preferred)"""
        dates = []
        current = self.season.start_date
        
        while current <= self.season.end_date:
            # 5 = Saturday, 6 = Sunday
            if self.config.prefer_weekends:
                if current.weekday() in [5, 6]:
                    dates.append(current)
            else:
                dates.append(current)
            current += timedelta(days=1)
        
        return dates
    
    def _create_variables(self):
        """Create decision variables for the CP model"""
        available_dates = self._get_available_dates()
        num_dates = len(available_dates)
        num_time_slots = len(self.config.valid_time_slots)
        
        # For each round, for each possible pairing
        for round_num in range(self.total_rounds):
            for i in range(self.num_teams_adjusted):
                for j in range(self.num_teams_adjusted):
                    if i != j:
                        # Binary variable: does this match exist in this round?
                        match_var = self.model.NewBoolVar(f'match_r{round_num}_h{i}_a{j}')
                        self.matches[(round_num, i, j)] = match_var
                        
                        # Date variable (index into available_dates)
                        date_var = self.model.NewIntVar(0, num_dates - 1, f'date_r{round_num}_h{i}_a{j}')
                        self.match_dates[(round_num, i, j)] = date_var
                        
                        # Time slot variable
                        time_var = self.model.NewIntVar(0, num_time_slots - 1, f'time_r{round_num}_h{i}_a{j}')
                        self.match_times[(round_num, i, j)] = time_var
    
    def _add_hard_constraints(self):
        """Add hard constraints that MUST be satisfied"""
        
        # CONSTRAINT 1: Each team plays exactly once per round (as home OR away)
        for round_num in range(self.total_rounds):
            for team in range(self.num_teams_adjusted):
                # Sum of matches where team is home or away = 1
                matches_as_home = [
                    self.matches[(round_num, team, opponent)]
                    for opponent in range(self.num_teams_adjusted)
                    if opponent != team
                ]
                matches_as_away = [
                    self.matches[(round_num, opponent, team)]
                    for opponent in range(self.num_teams_adjusted)
                    if opponent != team
                ]
                self.model.Add(sum(matches_as_home + matches_as_away) == 1)
        
        # CONSTRAINT 2: Each pair plays exactly 'legs' times (with reversed home/away)
        for i in range(self.num_teams_adjusted):
            for j in range(i + 1, self.num_teams_adjusted):
                # Team i vs Team j: i home, j away
                matches_i_home = [
                    self.matches[(r, i, j)]
                    for r in range(self.total_rounds)
                ]
                # Team j vs Team i: j home, i away
                matches_j_home = [
                    self.matches[(r, j, i)]
                    for r in range(self.total_rounds)
                ]
                
                # Each direction exactly once per leg
                self.model.Add(sum(matches_i_home) == self.config.legs // 2 + (1 if self.config.legs % 2 else 0))
                self.model.Add(sum(matches_j_home) == self.config.legs // 2)
        
        # CONSTRAINT 3: Minimum rest days between matches for same team
        available_dates = self._get_available_dates()
        
        for team in range(self.num_teams_adjusted):
            # Get all matches involving this team
            team_matches = []
            for round_num in range(self.total_rounds):
                for opponent in range(self.num_teams_adjusted):
                    if opponent != team:
                        # Match where team is home
                        if (round_num, team, opponent) in self.matches:
                            team_matches.append((round_num, team, opponent))
                        # Match where team is away
                        if (round_num, opponent, team) in self.matches:
                            team_matches.append((round_num, opponent, team))
            
            # For consecutive matches, ensure minimum rest period
            for idx in range(len(team_matches) - 1):
                match1 = team_matches[idx]
                match2 = team_matches[idx + 1]
                
                # Only apply if both matches are scheduled
                date1_var = self.match_dates[match1]
                date2_var = self.match_dates[match2]
                
                # date2 - date1 >= min_rest_days + 1 (match takes 1 day)
                self.model.Add(date2_var - date1_var >= self.config.min_rest_days + 1)
    
    def _add_soft_constraints(self):
        """Add soft constraints for optimization"""
        
        # OBJECTIVE: Minimize imbalance in home/away games throughout the season
        imbalance_vars = []
        
        for team in range(self.num_teams_adjusted):
            # Count home vs away games
            home_games = []
            away_games = []
            
            for round_num in range(self.total_rounds):
                for opponent in range(self.num_teams_adjusted):
                    if opponent != team:
                        if (round_num, team, opponent) in self.matches:
                            home_games.append(self.matches[(round_num, team, opponent)])
                        if (round_num, opponent, team) in self.matches:
                            away_games.append(self.matches[(round_num, opponent, team)])
            
            # Create variable for imbalance
            imbalance = self.model.NewIntVar(-self.total_rounds, self.total_rounds, f'imbalance_t{team}')
            self.model.Add(imbalance == sum(home_games) - sum(away_games))
            
            # Add absolute value to minimize
            abs_imbalance = self.model.NewIntVar(0, self.total_rounds, f'abs_imbalance_t{team}')
            self.model.AddAbsEquality(abs_imbalance, imbalance)
            imbalance_vars.append(abs_imbalance)
        
        # Minimize total imbalance
        self.model.Minimize(sum(imbalance_vars))
    
    def generate(self) -> Tuple[bool, List[Dict], str]:
        """
        Generate the schedule
        
        Returns:
            (success, matches_data, message)
            matches_data: List of dicts with match information
        """
        # Create variables
        self._create_variables()
        
        # Add constraints
        self._add_hard_constraints()
        self._add_soft_constraints()
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0  # 1 minute timeout
        solver.parameters.num_search_workers = 4  # Use multiple threads
        
        status = solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            # Extract solution
            matches_data = self._extract_solution(solver)
            
            if status == cp_model.OPTIMAL:
                message = f"✅ Tìm thấy lịch thi đấu TỐI ƯU với {len(matches_data)} trận đấu"
            else:
                message = f"✅ Tìm thấy lịch thi đấu KHẢ THI với {len(matches_data)} trận đấu"
            
            return True, matches_data, message
        else:
            if status == cp_model.INFEASIBLE:
                return False, [], "❌ Không tìm được lịch thi đấu hợp lệ (INFEASIBLE)"
            elif status == cp_model.MODEL_INVALID:
                return False, [], "❌ Mô hình không hợp lệ"
            else:
                return False, [], "❌ Không tìm được giải pháp trong thời gian cho phép"
    
    def _extract_solution(self, solver: cp_model.CpSolver) -> List[Dict]:
        """Extract match data from solver solution"""
        available_dates = self._get_available_dates()
        matches_data = []
        
        for round_num in range(self.total_rounds):
            for i in range(self.num_teams_adjusted):
                for j in range(self.num_teams_adjusted):
                    if i != j and (round_num, i, j) in self.matches:
                        match_var = self.matches[(round_num, i, j)]
                        
                        if solver.Value(match_var):  # This match is scheduled
                            # Skip bye matches (when team index >= actual teams)
                            if i >= len(self.teams) or j >= len(self.teams):
                                continue
                            
                            home_team = self.teams[i]
                            away_team = self.teams[j]
                            
                            # Get date and time
                            date_idx = solver.Value(self.match_dates[(round_num, i, j)])
                            time_idx = solver.Value(self.match_times[(round_num, i, j)])
                            
                            match_date = available_dates[date_idx]
                            time_slot = self.config.valid_time_slots[time_idx]
                            
                            match_datetime = datetime.combine(
                                match_date,
                                datetime.min.time().replace(hour=time_slot[0], minute=time_slot[1])
                            )
                            
                            matches_data.append({
                                'season': self.season,
                                'home_team': home_team,
                                'away_team': away_team,
                                'match_date': timezone.make_aware(match_datetime),
                                'round_number': round_num + 1,
                                'status': 'SCHEDULED'
                            })
        
        return matches_data


def get_schedule_config_from_settings() -> ScheduleConfig:
    """Load schedule configuration from SystemSettings"""
    
    # Default values
    default_times = [(17, 0), (18, 0), (19, 15), (20, 0)]
    default_min_rest = 5
    default_max_rest = 7
    
    try:
        # Try to load from settings
        time_setting = SystemSetting.objects.filter(key='MATCH_VALID_TIMES').first()
        if time_setting:
            # Parse "17:00,18:00,19:15,20:00"
            times_str = time_setting.value.split(',')
            default_times = []
            for t in times_str:
                h, m = t.strip().split(':')
                default_times.append((int(h), int(m)))
        
        min_rest_setting = SystemSetting.objects.filter(key='MIN_REST_DAYS').first()
        if min_rest_setting:
            default_min_rest = int(min_rest_setting.value)
        
        max_rest_setting = SystemSetting.objects.filter(key='MAX_REST_DAYS').first()
        if max_rest_setting:
            default_max_rest = int(max_rest_setting.value)
    except Exception:
        pass  # Use defaults if settings don't exist
    
    return ScheduleConfig(
        valid_time_slots=default_times,
        min_rest_days=default_min_rest,
        max_rest_days=default_max_rest,
        prefer_weekends=True,
        legs=2
    )
