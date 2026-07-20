from rest_framework import serializers


class AnalyticsFilterSerializer(serializers.Serializer):
    metric = serializers.ChoiceField(choices=["attainment", "grade_distribution", "coverage"])
    cohort = serializers.CharField(max_length=20, required=False)
    semester = serializers.CharField(max_length=20, required=False)
    course = serializers.CharField(max_length=40, required=False)
    outcome = serializers.CharField(max_length=24, required=False)


class TraceFilterSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=["forward", "backward"], default="forward")
    start = serializers.CharField(max_length=160, required=False)
