from rest_framework import serializers


class AcademicFeedbackInputSerializer(serializers.Serializer):
    anonymous = serializers.BooleanField(default=False)
    retaliation_risk = serializers.BooleanField(default=False)
    period = serializers.CharField(max_length=40)
    course_offering_id = serializers.CharField(max_length=120, required=False, allow_blank=True)
    category = serializers.CharField(max_length=40)
    description = serializers.CharField(max_length=5000)
    evidence = serializers.JSONField(default=list)
    impact = serializers.CharField(max_length=2000)
