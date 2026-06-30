from rest_framework.response import Response
from rest_framework.views import APIView


class APIRootView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(
            {
                "name": "intelligent_patient_flow_backend",
                "version": "v1",
                "status": "foundation-ready",
            }
        )
