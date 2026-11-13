import 'package:flutter_test/flutter_test.dart';
import 'package:gari_mobile/core/constants.dart';
import 'package:gari_mobile/models/task_model.dart';
import 'package:gari_mobile/models/organization_model.dart';
import 'package:gari_mobile/models/knowledge_article_model.dart';
import 'package:gari_mobile/models/community_post_model.dart';
import 'package:gari_mobile/models/subscription_usage_model.dart';
import 'package:gari_mobile/models/diagnosis_history_model.dart';

void main() {
  group('Module 13 Mobile Parity - Models & Core Contracts', () {
    test('1. Primary crops list supports all 7 core crops + Auto Detect', () {
      final crops = AppConstants.primaryCrops;
      expect(crops.length, equals(8));
      final cropIds = crops.map((c) => c.id).toSet();
      expect(cropIds.contains('all'), isTrue);
      expect(cropIds.contains('coffee'), isTrue);
      expect(cropIds.contains('pepper'), isTrue);
      expect(cropIds.contains('rice'), isTrue);
      expect(cropIds.contains('durian'), isTrue);
      expect(cropIds.contains('tomato'), isTrue);
      expect(cropIds.contains('chili'), isTrue);
      expect(cropIds.contains('corn'), isTrue);
    });

    test('2. TaskModel parses backend payload and supports completion/priority', () {
      final json = {
        'id': 101,
        'title': 'Phun phòng trừ rệp sáp cà phê',
        'description': 'Sử dụng chế phẩm nấm ký sinh Beauveria bassiana',
        'priority': 'HIGH',
        'due_date': '2026-11-10',
        'status': 'pending',
        'farm_id': 12,
        'farm_name': 'Nông trại Cà Phê Cư M\'gar',
        'created_at': '2026-11-04T08:00:00Z',
      };

      final task = TaskModel.fromJson(json);
      expect(task.id, equals(101));
      expect(task.title, equals('Phun phòng trừ rệp sáp cà phê'));
      expect(task.priority, equals('HIGH'));
      expect(task.isCompleted, isFalse);
      expect(task.farmId, equals(12));

      final completedTask = task.copyWith(status: 'completed');
      expect(completedTask.isCompleted, isTrue);
    });

    test('3. OrganizationModel parses hierarchical membership & role permissions', () {
      final json = {
        'id': 5,
        'name': 'Hợp Tác Xã Nông Nghiệp Hữu Cơ Đắk Lắk',
        'slug': 'htx-nong-nghiep-dak-lak',
        'organization_type': 'cooperative',
        'owner_id': 1,
        'plan_id': 'organization',
        'member_count': 18,
        'farms_count': 6,
        'role': 'farm_manager',
      };

      final org = OrganizationModel.fromJson(json);
      expect(org.id, equals(5));
      expect(org.name, contains('Đắk Lắk'));
      expect(org.orgType, equals('cooperative'));
      expect(org.memberCount, equals(18));
      expect(org.farmsCount, equals(6));
      expect(org.userRole, equals('farm_manager'));
      expect(org.canManageTasks, isTrue);
      expect(org.isOwner, isFalse);
    });

    test('4. KnowledgeArticleModel parses official guidance and metadata', () {
      final json = {
        'id': 42,
        'title': 'Quy trình phòng ngừa bệnh thán thư trên cây ớt VietGAP',
        'crop_id': 'chili',
        'category': 'pest_management',
        'summary': 'Biện pháp canh tác luân canh kết hợp phòng trừ sinh học.',
        'content': '1. Thu dọn tàn dư vụ trước.\n2. Phun phòng nấm Trichoderma.\n3. Duy trì thoát nước mặt liếp.',
        'author_name': 'TS. Nguyễn Văn A - Viện BVTV',
        'is_official_guidance': true,
        'source_citation': 'Cẩm nang BVTV 2026',
      };

      final article = KnowledgeArticleModel.fromJson(json);
      expect(article.id, equals(42));
      expect(article.cropId, equals('chili'));
      expect(article.isOfficialGuidance, isTrue);
      expect(article.authorName, contains('Nguyễn Văn A'));
      expect(article.sourceCitation, equals('Cẩm nang BVTV 2026'));
    });

    test('5. CommunityPostModel parses feed question and like toggle', () {
      final json = {
        'id': 88,
        'title': 'Lá sầu riêng Ri6 bị vàng chóp lá là thiếu vi lượng hay cháy lá?',
        'content': 'Vườn sầu riêng 3 năm tuổi tại Cai Lậy, xuất hiện vàng rìa lá già.',
        'crop_id': 'durian',
        'region': 'Đồng bằng Sông Cửu Long',
        'author_id': 14,
        'author_name': 'Nông Dân Ba Tri',
        'is_expert': false,
        'likes_count': 7,
        'comments_count': 3,
        'created_at': '2026-11-04T07:30:00Z',
        'is_liked': false,
      };

      final post = CommunityPostModel.fromJson(json);
      expect(post.id, equals(88));
      expect(post.cropId, equals('durian'));
      expect(post.likesCount, equals(7));
      expect(post.isLiked, isFalse);

      final likedPost = post.copyWith(isLiked: true, likesCount: 8);
      expect(likedPost.isLiked, isTrue);
      expect(likedPost.likesCount, equals(8));
    });

    test('6. SubscriptionUsageModel parses 7-dimension usage metrics & upgrade guidance', () {
      final json = {
        'entitlement': {
          'plan_id': 'pro',
          'plan_name': 'Gói Pro Nông Hộ',
        },
        'metrics': {
          'ai_usage': {'label': 'Câu hỏi AI', 'unit': 'lượt', 'used': 45, 'limit': 200, 'percentage': 22.5, 'is_unlimited': false, 'is_exhausted': false},
          'diagnosis': {'label': 'Chẩn đoán bệnh lá', 'unit': 'lượt', 'used': 80, 'limit': 100, 'percentage': 80.0, 'is_unlimited': false, 'is_exhausted': false},
          'farms': {'label': 'Trang trại', 'unit': 'trang trại', 'used': 2, 'limit': 5, 'percentage': 40.0, 'is_unlimited': false, 'is_exhausted': false},
          'plots': {'label': 'Phân lô / Vùng trồng', 'unit': 'lô', 'used': 8, 'limit': 20, 'percentage': 40.0, 'is_unlimited': false, 'is_exhausted': false},
          'organization_seats': {'label': 'Thành viên tổ chức', 'unit': 'thành viên', 'used': 1, 'limit': 3, 'percentage': 33.3, 'is_unlimited': false, 'is_exhausted': false},
          'storage_mb': {'label': 'Dung lượng lưu trữ', 'unit': 'MB', 'used': 120.5, 'limit': 500, 'percentage': 24.1, 'is_unlimited': false, 'is_exhausted': false},
          'expert_consultations': {'label': 'Tư vấn Chuyên gia', 'unit': 'phiên', 'used': 3, 'limit': 5, 'percentage': 60.0, 'is_unlimited': false, 'is_exhausted': false},
        },
        'upgrade_guidance': {
          'needs_upgrade': true,
          'suggested_plan_name': 'Gói Ultra',
          'suggested_plan_price': 199000,
        }
      };

      final sub = SubscriptionUsageModel.fromJson(json);
      expect(sub.planId, equals('pro'));
      expect(sub.planName, equals('Gói Pro Nông Hộ'));
      expect(sub.metrics.length, equals(7));
      expect(sub.metrics['diagnosis']!.percentage, equals(80.0));
      expect(sub.needsUpgrade, isTrue);
      expect(sub.suggestedPlanName, equals('Gói Ultra'));
    });

    test('7. DiagnosisHistoryModel parses scan records and calculates health status', () {
      final jsonHealthy = {
        'id': 1,
        'crop_id': 'rice',
        'crop_name': 'Lúa',
        'predicted_disease': 'Healthy Leaf',
        'disease_name_vi': 'Lá lúa khỏe mạnh',
        'confidence': 0.985,
        'confidence_percent': 98.5,
        'severity': 'LOW',
        'created_at': '2026-11-04T06:00:00Z',
      };

      final healthyDiag = DiagnosisHistoryModel.fromJson(jsonHealthy);
      expect(healthyDiag.isHealthy, isTrue);
      expect(healthyDiag.confidencePercent, equals(98.5));

      final jsonDisease = {
        'id': 2,
        'crop_id': 'pepper',
        'crop_name': 'Hồ tiêu',
        'predicted_disease': 'Foot Rot (Phytophthora)',
        'disease_name_vi': 'Bệnh chết nhanh (Phytophthora)',
        'confidence': 0.942,
        'confidence_percent': 94.2,
        'severity': 'HIGH',
        'created_at': '2026-11-04T07:00:00Z',
      };

      final diseasedDiag = DiagnosisHistoryModel.fromJson(jsonDisease);
      expect(diseasedDiag.isHealthy, isFalse);
      expect(diseasedDiag.severity, equals('HIGH'));
    });
  });
}
