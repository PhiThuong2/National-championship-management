import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from quanly.models import Season, Match, Team, Player, MatchEvent, MatchEventType, PlayerStat, MatchStatus

class Command(BaseCommand):
    help = 'Tự động tạo dữ liệu kết quả trận đấu giả định cho vòng 11-20 (logic theo vị trí)'

    def handle(self, *args, **kwargs):
        self.stdout.write("Bắt đầu tạo dữ liệu kết quả trận đấu Vòng 11-20...")

        season = Season.objects.filter(is_active=True).first()
        if not season:
            season = Season.objects.order_by('-start_date').first()

        teams = list(Team.objects.all())

        for round_num in range(11, 21):
            self.stdout.write(f"--- Đang xử lý Vòng {round_num} ---")
            
            matches = Match.objects.filter(season=season, round_number=round_num)
            
            if not matches.exists():
                self.stdout.write(f"Vòng {round_num} chưa có lịch. Đang tạo lịch ngẫu nhiên...")
                random.shuffle(teams)
                matches_to_create = []
                for i in range(0, len(teams), 2):
                    if i + 1 < len(teams):
                        match_date = timezone.now() + timezone.timedelta(days=(round_num)*3) # Future dates roughly
                        # But for results we need them to be 'finished', so maybe past dates?
                        # User said "add data results", implying they are played.
                        match_date = timezone.now() - timezone.timedelta(days=(21-round_num)*2)

                        m = Match(
                            season=season,
                            home_team=teams[i],
                            away_team=teams[i+1],
                            round_number=round_num,
                            match_date=match_date,
                            status=MatchStatus.SCHEDULED
                        )
                        m.save()
                        matches_to_create.append(m)
                matches = matches_to_create
            
            for match in matches:
                if match.status == 'FINISHED':
                    continue

                # Random Score
                home_goals = random.choices([0, 1, 2, 3, 4], weights=[20, 30, 30, 15, 5])[0]
                away_goals = random.choices([0, 1, 2, 3], weights=[30, 40, 20, 10])[0]
                
                match.home_score = home_goals
                match.away_score = away_goals
                match.status = MatchStatus.FINISHED
                match.save()
                
                self.stdout.write(f"Updated: {match.home_team.name} {home_goals} - {away_goals} {match.away_team.name}")

                # 1. Goals (Ưu tiên Tiền đạo)
                self.create_goals(match, match.home_team, home_goals, season)
                self.create_goals(match, match.away_team, away_goals, season)
                
                # 2. Cards (Thẻ phạt - Random)
                self.create_cards(match, match.home_team, season)
                self.create_cards(match, match.away_team, season)

                # 3. Interceptions (Ưu tiên Hậu vệ)
                self.create_interceptions(match, match.home_team, season)
                self.create_interceptions(match, match.away_team, season)
                
                # 4. Saves (Chỉ Thủ môn)
                self.create_saves(match, match.home_team, season)
                self.create_saves(match, match.away_team, season)

                # 5. Matches Played
                self.update_matches_played(match, match.home_team, season)
                self.update_matches_played(match, match.away_team, season)

        self.stdout.write(self.style.SUCCESS("Hoàn tất!"))

    def create_goals(self, match, team, goals_count, season):
        if goals_count == 0: return
        players = list(Player.objects.filter(team=team))
        if not players: return

        # Prioritize Forwards (FW), then Midfielders (MF)
        forwards = [p for p in players if p.position == 'Forward']
        midfielders = [p for p in players if p.position == 'Midfielder']
        others = [p for p in players if p.position not in ['Forward', 'Midfielder']]
        
        # Weighted choice: FW 70%, MF 25%, Others 5%
        pool = forwards * 14 + midfielders * 5 + others * 1
        if not pool: pool = players

        for _ in range(goals_count):
            scorer = random.choice(pool)
            minute = random.randint(1, 90)
            
            MatchEvent.objects.create(
                match=match, player=scorer, team=team,
                event_type=MatchEventType.GOAL, minute=minute
            )
            stat, _ = PlayerStat.objects.get_or_create(player=scorer, season=season)
            stat.goals += 1
            stat.save()
            
            # Assists (Prioritize Midfielders)
            if len(players) > 1 and random.choice([True, False]): # 50% assist chance
                assist_pool = midfielders * 8 + forwards * 2 + others * 1
                if not assist_pool: assist_pool = [p for p in players if p != scorer]
                assist_pool = [p for p in assist_pool if p != scorer] # Cannot assist self (usually)
                
                if assist_pool:
                    assist_player = random.choice(assist_pool)
                    MatchEvent.objects.create(
                        match=match, player=assist_player, team=team,
                        event_type=MatchEventType.ASSIST, minute=minute
                    )
                    stat_ast, _ = PlayerStat.objects.get_or_create(player=assist_player, season=season)
                    stat_ast.assists += 1
                    stat_ast.save()

    def create_interceptions(self, match, team, season):
        # Ưu tiên Hậu vệ (Defender)
        players = list(Player.objects.filter(team=team))
        defenders = [p for p in players if p.position == 'Defender']
        others = [p for p in players if p.position != 'Defender']
        
        if not defenders and not others: return
        
        pool = defenders * 9 + others * 1 
        
        count = random.randint(5, 15) # More interruptions in a game
        for _ in range(count):
            p = random.choice(pool)
            MatchEvent.objects.create(
                match=match, player=p, team=team,
                event_type=MatchEventType.INTERCEPTION, minute=random.randint(1, 90)
            )
            # Note: PlayerStat might not have 'interceptions' field explicitly counted? 
            # Checked models previously, PlayerStat has 'saves', 'goals', 'assists', 'yellow', 'red', 'matches_played'.
            # It DOES NOT seem to have 'interceptions' count in PlayerStat model based on previous `models.py` view (lines 193-200+).
            # The homepage calculates it dynamically from MatchEvent in `get_top_interceptions` (now changed to Goalkeepers, but user asked for "đánh chặn" for defenders).
            # User request: "đánh chặn (ưu tiên hậu vệ)".
            # I should create the EVENTS. The stats page calculates from events if I recall `get_top_interceptions`.
            # Wait, step 1067 view of `utils.py` showed `get_top_interceptions` counting from MatchEvent. 
            # So creating events is enough.

    def create_saves(self, match, team, season):
        # Chỉ thủ môn (Goalkeeper)
        gks = list(Player.objects.filter(team=team, position='Goalkeeper'))
        if not gks: return
        
        gk = gks[0] # Main GK
        saves_count = random.randint(2, 8)
        
        stat, _ = PlayerStat.objects.get_or_create(player=gk, season=season)
        stat.saves += saves_count
        stat.save()
        
        # Create events specific for SAVE is 'Cản phá'
        for _ in range(saves_count):
             MatchEvent.objects.create(
                match=match, player=gk, team=team,
                event_type=MatchEventType.SAVE, minute=random.randint(1, 90)
            )

    def create_cards(self, match, team, season):
        players = list(Player.objects.filter(team=team))
        if not players: return
        
        # Yellow
        count = random.choices([0, 1, 2, 3], weights=[30, 40, 20, 10])[0]
        for _ in range(count):
            p = random.choice(players)
            MatchEvent.objects.create(
                match=match, player=p, team=team,
                event_type=MatchEventType.YELLOW_CARD, minute=random.randint(1, 90)
            )
            stat, _ = PlayerStat.objects.get_or_create(player=p, season=season)
            stat.yellow_cards += 1
            stat.save()
            
    def update_matches_played(self, match, team, season):
        players = list(Player.objects.filter(team=team))
        if not players: return
        played = random.sample(players, k=min(len(players), 15))
        for p in played:
            stat, _ = PlayerStat.objects.get_or_create(player=p, season=season)
            stat.matches_played += 1
            stat.save()
