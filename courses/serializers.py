from courses.models import Category, Course, User, UserCourse, Forum, Comment, Chapter, Lesson, LessonProgress
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
import cloudinary
import cloudinary.uploader


class BaseSerializer(serializers.ModelSerializer):
    def upload_to_cloudinary(self, image_file, folder="uploads"):
        try:
            upload_result = cloudinary.uploader.upload(
                image_file,
                folder=folder,
                resource_type="image",
                transformation=[
                    {'width': 500, 'height': 500, 'crop': 'limit'},
                    {'quality': 'auto'}
                ]
            )
            return upload_result.get('secure_url')
        except Exception as e:
            raise serializers.ValidationError(f"Lỗi khi upload ảnh: {str(e)}")

    def handle_image_upload(self, validated_data, field_name, folder="uploads"):
        if field_name in validated_data and validated_data[field_name]:
            image_file = validated_data[field_name]
            secure_url = self.upload_to_cloudinary(image_file, folder)
            validated_data[field_name] = secure_url
        return validated_data


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name']


class ItemSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)

        data['image'] = instance.image.url

        return data


class CourseSerializer(ItemSerializer):
    lecturer_name = serializers.SerializerMethodField(read_only=True)
    category_name = serializers.SerializerMethodField(read_only=True)
    total_student = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'subject', 'image', 'category', 'category_name', 'total_student', 'lecturer', 'lecturer_name', 'name', 'description', 'price', 'level', 'duration',
                  'created_at']

    def get_lecturer_name(self, obj):
        return obj.lecturer.last_name + " " + obj.lecturer.first_name

    def get_total_student(self, obj):
        return obj.user_course.count()

    def get_category_name(self, obj):
        return obj.category.name

    def get_extra_kwargs(self):
        extra_kwargs = super().get_extra_kwargs()
        request = self.context.get('request')

        if request and request.method in ['PUT', 'PATCH']:
            extra_kwargs['subject'] = {'required': False}
            extra_kwargs['image'] = {'required': False}

        return extra_kwargs


class ChapterSerializer(BaseSerializer):
    class Meta:
        model = Chapter
        fields = ['id', 'course', 'name', 'description', 'is_published', 'active', 'created_at']


class LessonSerializer(BaseSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'chapter', 'name', 'description', 'type', 'video_url', 'duration', 'is_published', 'active',
                  'created_at']


class LessonWithProgressSerializer(BaseSerializer):
    progress = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Lesson
        fields = ['id', 'chapter', 'name', 'description', 'type', 'video_url', 'duration', 'is_published', 'active',
                  'created_at', 'progress']
    
    def get_progress(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                progress = LessonProgress.objects.get(lesson=obj, user=request.user)
                return LessonProgressSerializer(progress).data
            except LessonProgress.DoesNotExist:
                return None
        return None


class LessonProgressSerializer(BaseSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = LessonProgress
        fields = ['id', 'lesson', 'user', 'status', 'status_display', 'started_at', 'completed_at', 'watch_time', 'created_at', 'updated_at']
        read_only_fields = ['user', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ChapterWithLessonsSerializer(BaseSerializer):
    lessons = LessonWithProgressSerializer(many=True, read_only=True)
    total_lessons = serializers.SerializerMethodField(read_only=True)
    completed_lessons = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Chapter
        fields = ['id', 'course', 'name', 'description', 'is_published', 'active', 'created_at', 
                  'lessons', 'total_lessons', 'completed_lessons']
    
    def get_total_lessons(self, obj):
        return obj.lessons.filter(is_published=True).count()
    
    def get_completed_lessons(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return LessonProgress.objects.filter(
                lesson__chapter=obj,
                lesson__is_published=True,
                user=request.user,
                status='COMPLETED'
            ).count()
        return 0


class UserRegistrationSerializer(BaseSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'confirm_password', 'email',
                  'first_name', 'last_name', 'avatar', 'address', 'introduce', 'phone', 'userRole')

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Mật khẩu xác nhận không khớp."})
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email này đã được sử dụng.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Tên đăng nhập này đã được sử dụng.")
        return value

    def create(self, validated_data):
        validated_data = self.handle_image_upload(validated_data, 'avatar', 'avatars')
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')

        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(BaseSerializer):
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'avatar', 'address', 'introduce', 'password', 'phone')

    def update(self, instance, validated_data):
        validated_data = self.handle_image_upload(validated_data, 'avatar', 'avatars')
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class UserSerializer(BaseSerializer):
    avatar = serializers.SerializerMethodField()
    userRole = serializers.SerializerMethodField(read_only=True)
    date_joined = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'avatar', 'address', 'introduce', 'phone', 'date_joined', 'userRole', 'is_active')
        read_only_fields = ('id', 'date_joined')

    def get_userRole(self, obj):
        return obj.userRole.name

    def get_date_joined(self, obj):
        return obj.date_joined.strftime("%d-%m-%Y")

    def get_avatar(self, obj):
        if obj.avatar:
            if isinstance(obj.avatar, str):
                return obj.avatar
            else:
                return obj.avatar.url if obj.avatar else None
        return None


class UserCourseSerializer(BaseSerializer):
    user = serializers.SerializerMethodField(read_only=True)
    course_obj = CourseSerializer(source='course', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_at = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserCourse
        fields = ['id', 'user', 'course', 'course_obj', 'status', 'status_display', 'created_at']

    def get_user(self, obj):
        return obj.user.username

    def get_created_at(self, obj):
        return obj.created_at.strftime("%d-%m-%Y")

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class UserNameMixin:
    def get_username(self, obj):
        return obj.user.username


class ForumSerializer(serializers.ModelSerializer, UserNameMixin):
    user = serializers.SerializerMethodField(read_only=True)
    course_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Forum
        fields = ['user', 'course', 'course_name', 'name', 'description', 'is_locked']

    def get_user(self, obj):
        return self.get_username(obj)

    def get_course_name(self, obj):
        return obj.course.name

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class CommentSerializer(serializers.ModelSerializer, UserNameMixin):
    user = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Comment
        fields = ['user', 'forum', 'parent', 'content']

    def get_user(self, obj):
        return self.get_username(obj)

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
