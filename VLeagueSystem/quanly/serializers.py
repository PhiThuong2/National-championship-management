from rest_framework import serializers
from .models import Team, Player, Contract, TransferRequest

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name', 'stadium', 'city', 'logo']

class PlayerSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    class Meta:
        model = Player
        fields = ['id', 'name', 'team', 'team_name', 'position', 'jersey_number', 'status']

class TransferRequestSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.name', read_only=True)
    from_team_name = serializers.CharField(source='from_team.name', read_only=True)
    to_team_name = serializers.CharField(source='to_team.name', read_only=True)
    class Meta:
        model = TransferRequest
        fields = '__all__'