from django.db.models import Count
from rest_framework import viewsets, generics, status, parsers, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from django.utils import timezone
import hmac, hashlib
from courses.models import Category, Course, User, Role, UserCourse, Forum, Comment, Chapter, Lesson, CourseStatus, LessonProgress
from courses import serializers, paginators
from .perms import IsAdmin, IsStudent, IsTeacher, IsTeacherOrAdmin
from .services.momo import create_momo_payment, update_status_user_course


class CategoryViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = Category.objects.filter(active=True)
    serializer_class = serializers.CategorySerializer


class TeacherViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = User.objects.filter(userRole__name="Teacher")
    serializer_class = serializers.TeacherSerializer


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.filter(active=True)
    serializer_class = serializers.CourseSerializer
    pagination_class = paginators.CoursePagination

    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return [IsTeacherOrAdmin()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(lecturer=self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.request

        lecturer_id = request.query_params.get('lecturer')
        category_id = request.query_params.get('category')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        level = request.query_params.get('level')

        if lecturer_id:
            queryset = queryset.filter(lecturer_id=lecturer_id)

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        if level:
            queryset = queryset.filter(level=level)

        return queryset

    @action(methods=['get'], detail=True, url_path='forum')
    def get_forum(self, request, pk=None):
        course = self.get_object()
        try:
            forum = course.forum
        except Forum.DoesNotExist:
            return Response({"detail": "Forum not found for this course"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializers.ForumSerializer(forum).data, status=status.HTTP_200_OK)

    @action(methods=['get'], detail=False, url_path='top')
    def get_courses_top(self, request, pk=None):
        top_courses = Course.objects.annotate(student_count=Count('user_course')).order_by('-student_count')[:3]
        return Response(serializers.CourseSerializer(top_courses, many=True).data, status=status.HTTP_200_OK)


class ChapterViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.ChapterSerializer
    pagination_class = paginators.ChapterPagination
    queryset = Chapter.objects.all()

    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    @action(methods=['get'], detail=True, url_path='lessons')
    def get_chapter_with_lessons(self, request, pk=None):
        """
        Get detailed chapter information with all lessons and progress
        """
        chapter = self.get_object()
        serializer = serializers.ChapterWithLessonsSerializer(
            chapter, 
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.LessonSerializer
    pagination_class = paginators.LessonPagination
    queryset = Lesson.objects.all()

    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]


class LessonProgressViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.LessonProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        lesson_id = self.request.query_params.get('lesson')
        
        queryset = LessonProgress.objects.filter(user=user)
        
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)
            
        return queryset

    def perform_create(self, serializer):
        # Get or create lesson progress
        lesson = serializer.validated_data['lesson']
        user = self.request.user
        
        lesson_progress, created = LessonProgress.objects.get_or_create(
            lesson=lesson,
            user=user,
            defaults=serializer.validated_data
        )
        
        if not created:
            # Update existing progress
            for attr, value in serializer.validated_data.items():
                setattr(lesson_progress, attr, value)
            lesson_progress.save()
        
        return lesson_progress

    @action(methods=['post'], detail=False, url_path='start-lesson')
    def start_lesson(self, request):
        """
        Start learning a lesson - updates status to IN_PROGRESS and sets started_at
        """
        lesson_id = request.data.get('lesson')
        if not lesson_id:
            return Response(
                {'error': 'lesson field is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': 'Lesson not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        lesson_progress, created = LessonProgress.objects.get_or_create(
            lesson=lesson,
            user=request.user,
            defaults={
                'status': 'IN_PROGRESS',
                'started_at': timezone.now()
            }
        )
        
        if not created and lesson_progress.status == 'NOT_STARTED':
            lesson_progress.status = 'IN_PROGRESS'
            lesson_progress.started_at = timezone.now()
            lesson_progress.save()
        
        serializer = self.get_serializer(lesson_progress)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['post'], detail=False, url_path='complete-lesson')
    def complete_lesson(self, request):
        """
        Complete a lesson - updates status to COMPLETED and sets completed_at
        """
        lesson_id = request.data.get('lesson')
        if not lesson_id:
            return Response(
                {'error': 'lesson field is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': 'Lesson not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        lesson_progress, created = LessonProgress.objects.get_or_create(
            lesson=lesson,
            user=request.user,
            defaults={
                'status': 'COMPLETED',
                'started_at': timezone.now(),
                'completed_at': timezone.now()
            }
        )
        
        if not created:
            lesson_progress.status = 'COMPLETED'
            lesson_progress.completed_at = timezone.now()
            if not lesson_progress.started_at:
                lesson_progress.started_at = timezone.now()
            lesson_progress.save()
        
        serializer = self.get_serializer(lesson_progress)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['patch'], detail=False, url_path='update-watch-time')
    def update_watch_time(self, request):
        """
        Update watch time for a lesson
        """
        lesson_id = request.data.get('lesson')
        watch_time = request.data.get('watch_time')
        
        if not lesson_id:
            return Response(
                {'error': 'lesson field is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if watch_time is None:
            return Response(
                {'error': 'watch_time field is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': 'Lesson not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        lesson_progress, created = LessonProgress.objects.get_or_create(
            lesson=lesson,
            user=request.user,
            defaults={
                'watch_time': watch_time,
                'status': 'IN_PROGRESS',
                'started_at': timezone.now()
            }
        )
        
        if not created:
            lesson_progress.watch_time = watch_time
            if lesson_progress.status == 'NOT_STARTED':
                lesson_progress.status = 'IN_PROGRESS'
                lesson_progress.started_at = timezone.now()
            lesson_progress.save()
        
        serializer = self.get_serializer(lesson_progress)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ViewSet, generics.CreateAPIView):
    queryset = User.objects.filter(is_active=True)
    serializer_class = serializers.UserSerializer
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    def get_serializer_class(self):
        if self.action in ['register_student', 'register_teacher']:
            return serializers.UserRegistrationSerializer
        return serializers.UserSerializer

    def get_permissions(self):
        if self.action in ['register_student', 'register_teacher']:
            return [permissions.AllowAny()]
        elif self.action in ['get_current_user']:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Vui lòng sử dụng /users/register-student/ hoặc /users/register-teacher/ để đăng ký."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    # Đăng ký học viên
    @action(methods=['post'], detail=False, url_path='register-student')
    def register_student(self, request):
        data = request.data.copy()
        student_role = get_object_or_404(Role, name="Student")
        data['userRole'] = student_role.pk
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Đăng ký học viên thành công!',
                'user': serializers.UserSerializer(user).data,
                'note': 'Vui lòng sử dụng endpoint /o/token/ để lấy access token sau khi đăng ký'
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Đăng ký giảng viên
    @action(methods=['post'], detail=False, url_path='register-teacher')
    def register_teacher(self, request):
        data = request.data.copy()
        teacher_role = get_object_or_404(Role, name="Teacher")
        data['userRole'] = teacher_role.pk
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Đăng ký giảng viên thành công!',
                'user': serializers.UserSerializer(user).data,
                'note': 'Vui lòng sử dụng endpoint /o/token/ để lấy access token sau khi đăng ký'
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['get', 'patch'], url_path='current-user', detail=False,
            permission_classes=[permissions.IsAuthenticated])
    def get_current_user(self, request):
        user = request.user
        if request.method == 'PATCH':
            serializer = serializers.UserUpdateSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializers.UserSerializer(user).data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.UserSerializer(user).data)


class UserCourseViewSet(viewsets.ViewSet, generics.ListAPIView, generics.RetrieveAPIView):
    serializer_class = serializers.UserCourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if IsAdmin().has_permission(self.request, self):
            return UserCourse.objects.all()
        return UserCourse.objects.filter(user=user)


    @action(methods=['post'], detail=False, url_path='create', permission_classes=[IsStudent])
    def create_user_course(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user_course = serializer.save()
        pay_url = create_momo_payment(user_course.course.price, user_course.id)

        return Response({'payUrl': pay_url}, status=status.HTTP_201_CREATED)


class MomoIPNViewSet(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        user_course_id = data['extraData']

        raw_signature = (
            f"accessKey=F8BBA842ECF85"
            f"&amount={data['amount']}"
            f"&extraData={data['extraData']}"
            f"&message={data['message']}"
            f"&orderId={data['orderId']}"
            f"&orderInfo={data['orderInfo']}"
            f"&orderType={data['orderType']}"
            f"&partnerCode={data['partnerCode']}"
            f"&payType={data['payType']}"
            f"&requestId={data['requestId']}"
            f"&responseTime={data['responseTime']}"
            f"&resultCode={data['resultCode']}"
            f"&transId={data['transId']}"
        )

        signature = hmac.new(bytes('K951B6PE1waDMi640xX08PD3vg6EkVlz', 'utf-8'),
                     bytes(raw_signature, 'utf-8'),
                     hashlib.sha256).hexdigest()

        # xác thực chữ
        if signature != data.get("signature"):
            return Response({"message": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        # thanh toán thành công
        if data["resultCode"] == 0:
            update_status_user_course(user_course_id, CourseStatus.IN_PROGRESS)
            return Response({"message": "Payment success"}, status=status.HTTP_200_OK)
        # thanh toán thất bại
        else:
            update_status_user_course(user_course_id, CourseStatus.PAYMENT_FAILED)
            return Response({"message": "Payment failed"}, status=status.HTTP_200_OK)


class ForumViewSet(viewsets.ViewSet, generics.ListCreateAPIView):
    serializer_class = serializers.ForumSerializer
    permission_classes = [IsTeacher]

    def get_queryset(self):
        user = self.request.user
        if IsTeacher().has_permission(self.request, self):
            return Forum.objects.filter(user=user)
        elif IsAdmin().has_permission(self.request, self):
            return Forum.objects.all()


class CommentViewSet(viewsets.ViewSet, generics.ListCreateAPIView):
    serializer_class = serializers.CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Comment.objects.filter(parent=None)

    @action(methods=['get'], detail=True, url_path='replies', permission_classes=[permissions.IsAuthenticated])
    def get_replies(self, request, pk=None):
        comment = self.get_object()
        try:
            relies = comment.replies
        except Comment.DoesNotExist:
            return Response('Comment not found relies', status=status.HTTP_200_OK)
        return Response(serializers.CommentSerializer(relies, many=True).data, status=status.HTTP_200_OK)