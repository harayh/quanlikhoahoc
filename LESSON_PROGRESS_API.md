# 📚 Lesson Progress Tracking APIs

## Overview

This implementation adds comprehensive lesson progress tracking functionality to the course management system. Users can now track their learning progress through individual lessons within chapters.

## 🎯 Key Features

- **Chapter Details with Lessons**: Get comprehensive chapter information including all lessons and progress
- **Lesson Progress Tracking**: Track individual lesson completion status and watch time
- **Automatic Timestamps**: System automatically records when lessons are started and completed
- **Progress Summary**: View completion statistics at the chapter level
- **Vietnamese Status Names**: User-friendly status displays in Vietnamese

## 🔗 New API Endpoints

### 1. Chapter Details with Lessons

```http
GET /chapters/{id}/lessons/
```

**Description**: Get detailed chapter information with all lessons and user progress

**Response Example**:
```json
{
  "id": 1,
  "name": "Introduction to Python",
  "description": "Basic Python programming concepts",
  "is_published": true,
  "lessons": [
    {
      "id": 1,
      "name": "Variables and Data Types",
      "description": "Learn about Python variables",
      "type": "video",
      "video_url": "https://example.com/video1.mp4",
      "duration": 300,
      "progress": {
        "id": 1,
        "status": "COMPLETED",
        "status_display": "Hoàn thành",
        "started_at": "2024-01-15T09:00:00Z",
        "completed_at": "2024-01-15T10:30:00Z",
        "watch_time": 250
      }
    }
  ],
  "total_lessons": 5,
  "completed_lessons": 1
}
```

### 2. Start Lesson

```http
POST /lesson-progress/start-lesson/
```

**Description**: Start learning a lesson - updates status to IN_PROGRESS

**Request Body**:
```json
{
  "lesson": 1
}
```

**Response Example**:
```json
{
  "id": 1,
  "lesson": 1,
  "user": 1,
  "status": "IN_PROGRESS",
  "status_display": "Đang học",
  "started_at": "2024-01-15T09:00:00Z",
  "completed_at": null,
  "watch_time": 0
}
```

### 3. Complete Lesson

```http
POST /lesson-progress/complete-lesson/
```

**Description**: Mark a lesson as completed - sets completion timestamp

**Request Body**:
```json
{
  "lesson": 1
}
```

**Response Example**:
```json
{
  "id": 1,
  "lesson": 1,
  "user": 1,
  "status": "COMPLETED",
  "status_display": "Hoàn thành",
  "started_at": "2024-01-15T09:00:00Z",
  "completed_at": "2024-01-15T10:30:00Z",
  "watch_time": 250
}
```

### 4. Update Watch Time

```http
PATCH /lesson-progress/update-watch-time/
```

**Description**: Update the watch time for a lesson (in seconds)

**Request Body**:
```json
{
  "lesson": 1,
  "watch_time": 150
}
```

**Response Example**:
```json
{
  "id": 1,
  "lesson": 1,
  "user": 1,
  "status": "IN_PROGRESS",
  "watch_time": 150,
  "started_at": "2024-01-15T09:00:00Z"
}
```

### 5. List Lesson Progress

```http
GET /lesson-progress/
```

**Description**: Get user's lesson progress across all lessons

**Query Parameters**:
- `lesson` (optional): Filter by specific lesson ID

**Examples**:
- `GET /lesson-progress/` - All user progress
- `GET /lesson-progress/?lesson=1` - Progress for lesson 1 only

**Response Example**:
```json
[
  {
    "id": 1,
    "lesson": 1,
    "user": 1,
    "status": "COMPLETED",
    "status_display": "Hoàn thành",
    "started_at": "2024-01-15T09:00:00Z",
    "completed_at": "2024-01-15T10:30:00Z",
    "watch_time": 250
  }
]
```

## 📊 Status Values

| Status | Display Name | Description |
|--------|--------------|-------------|
| `NOT_STARTED` | Chưa bắt đầu | Default status when lesson is first accessed |
| `IN_PROGRESS` | Đang học | When user starts watching the lesson |
| `COMPLETED` | Hoàn thành | When user finishes the lesson |

## 💡 Usage Examples

### Learning Flow Example

```javascript
// 1. Get chapter with lessons
const chapter = await fetch('/chapters/1/lessons/');

// 2. Start first lesson
await fetch('/lesson-progress/start-lesson/', {
  method: 'POST',
  body: JSON.stringify({ lesson: 1 })
});

// 3. Update watch time periodically
await fetch('/lesson-progress/update-watch-time/', {
  method: 'PATCH',
  body: JSON.stringify({ lesson: 1, watch_time: 120 })
});

// 4. Complete lesson
await fetch('/lesson-progress/complete-lesson/', {
  method: 'POST',
  body: JSON.stringify({ lesson: 1 })
});
```

### Progress Dashboard Example

```javascript
// Get completion summary
const chapter = await fetch('/chapters/1/lessons/');
const completionRate = chapter.completed_lessons / chapter.total_lessons;

// Get all user progress
const allProgress = await fetch('/lesson-progress/');
```

## 🔧 Implementation Details

### Models

- **LessonProgressStatus**: New status choices enum
- **LessonProgress**: Enhanced with status choices and unique constraint
- **Meta.unique_together**: Prevents duplicate progress records per user/lesson

### Serializers

- **LessonProgressSerializer**: Handles lesson progress CRUD operations
- **LessonWithProgressSerializer**: Includes progress data with lesson information
- **ChapterWithLessonsSerializer**: Provides chapter with lessons and progress summary

### ViewSets

- **LessonProgressViewSet**: Complete CRUD with custom actions for progress management
- **ChapterViewSet**: Enhanced with lesson details action

### Permissions

- All endpoints require authentication
- Progress data is automatically filtered by authenticated user
- Teachers and admins can manage lessons but not user progress

## ✅ Testing

All components have been tested for:
- ✅ Model relationships and constraints
- ✅ Serializer functionality and field validation
- ✅ ViewSet methods and custom actions
- ✅ URL routing and reverse resolution
- ✅ Integration between all components

## 📱 Frontend Integration

The APIs are designed to support common learning management features:

- **Video Player Integration**: Update watch time as user progresses through videos
- **Progress Bars**: Show completion percentage at chapter and course levels
- **Learning Dashboard**: Display user's overall learning progress
- **Lesson Navigation**: Track which lessons are completed vs in-progress
- **Resume Learning**: Know where user left off in their learning journey

## 🚀 Ready for Production

The implementation follows Django REST Framework best practices and is ready for immediate use in production environments.