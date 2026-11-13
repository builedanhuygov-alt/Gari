import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'constants.dart';
import '../models/user_model.dart';
import '../models/diagnosis_result.dart';
import '../models/farm_model.dart';
import '../models/task_model.dart';
import '../models/organization_model.dart';
import '../models/chat_message.dart';
import '../models/notification_model.dart';
import '../models/community_post_model.dart';
import '../models/knowledge_article_model.dart';
import '../models/subscription_usage_model.dart';
import '../models/diagnosis_history_model.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  String _baseUrl = AppConstants.defaultBaseUrl;
  String? _token;
  UserModel? _currentUser;

  String get baseUrl => _baseUrl;
  String? get token => _token;
  UserModel? get currentUser => _currentUser;
  bool get isAuthenticated => _token != null && _token!.isNotEmpty;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString(AppConstants.serverUrlKey) ?? AppConstants.defaultBaseUrl;
    _token = prefs.getString(AppConstants.tokenKey);
    final userJson = prefs.getString(AppConstants.userKey);
    if (userJson != null) {
      try {
        _currentUser = UserModel.fromJson(jsonDecode(userJson));
      } catch (_) {}
    }
  }

  Future<void> setBaseUrl(String url) async {
    _baseUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConstants.serverUrlKey, _baseUrl);
  }

  Map<String, String> _headers({bool jsonContent = true}) {
    final h = <String, String>{
      'Accept': 'application/json',
    };
    if (jsonContent) {
      h['Content-Type'] = 'application/json';
    }
    if (_token != null && _token!.isNotEmpty) {
      h['Authorization'] = 'Bearer $_token';
    }
    return h;
  }

  // --- 1. AUTHENTICATION & PROFILE ---
  Future<Map<String, dynamic>> login(String email, String password) async {
    final url = Uri.parse('$_baseUrl/api/auth/login');
    final res = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    final data = jsonDecode(utf8.decode(res.bodyBytes));
    if (res.statusCode == 200 && data['success'] == true) {
      _token = data['token'];
      _currentUser = UserModel.fromJson(data['user']);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(AppConstants.tokenKey, _token!);
      await prefs.setString(AppConstants.userKey, jsonEncode(_currentUser!.toJson()));
      return {'success': true, 'user': _currentUser};
    }
    return {'success': false, 'message': data['detail'] ?? 'Đăng nhập không thành công'};
  }

  Future<Map<String, dynamic>> register({
    required String email,
    required String password,
    required String fullName,
    String accountType = 'farmer',
  }) async {
    final url = Uri.parse('$_baseUrl/api/auth/register');
    final res = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
        'confirm_password': password,
        'full_name': fullName,
        'account_type': accountType,
      }),
    );
    final data = jsonDecode(utf8.decode(res.bodyBytes));
    if (res.statusCode == 200 && data['success'] == true) {
      _token = data['token'];
      _currentUser = UserModel.fromJson(data['user']);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(AppConstants.tokenKey, _token!);
      await prefs.setString(AppConstants.userKey, jsonEncode(_currentUser!.toJson()));
      return {'success': true, 'user': _currentUser};
    }
    return {'success': false, 'message': data['detail'] ?? 'Đăng ký không thành công'};
  }

  Future<UserModel?> getProfile() async {
    if (!isAuthenticated) return null;
    final url = Uri.parse('$_baseUrl/api/auth/profile');
    final res = await http.get(url, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final userObj = data['user'] ?? (data.containsKey('id') ? data : null);
      if (userObj != null) {
        _currentUser = UserModel.fromJson(userObj);
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(AppConstants.userKey, jsonEncode(_currentUser!.toJson()));
        return _currentUser;
      }
    }
    return _currentUser;
  }

  Future<void> logout() async {
    if (isAuthenticated) {
      try {
        final url = Uri.parse('$_baseUrl/api/auth/logout');
        await http.post(url, headers: _headers());
      } catch (_) {}
    }
    _token = null;
    _currentUser = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConstants.tokenKey);
    await prefs.remove(AppConstants.userKey);
  }

  // --- 2. AI LEAF INTELLIGENCE DIAGNOSIS ---
  Future<DiagnosisResult> predictLeaf({
    required Uint8List imageBytes,
    required String filename,
    String? cropFilter,
    int? farmId,
    int? plotId,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/predict');
    final req = http.MultipartRequest('POST', uri);

    if (_token != null && _token!.isNotEmpty) {
      req.headers['Authorization'] = 'Bearer $_token';
    }

    if (cropFilter != null && cropFilter != 'Tự động nhận diện' && cropFilter != 'all') {
      req.fields['crop_filter'] = cropFilter;
    }
    if (farmId != null) {
      req.fields['farm_id'] = farmId.toString();
    }
    if (plotId != null) {
      req.fields['plot_id'] = plotId.toString();
    }

    final ext = filename.split('.').last.toLowerCase();
    final mimeType = (ext == 'png') ? 'image/png' : 'image/jpeg';

    req.files.add(http.MultipartFile.fromBytes(
      'file',
      imageBytes,
      filename: filename,
      contentType: MediaType.parse(mimeType),
    ));

    final streamedRes = await req.send();
    final res = await http.Response.fromStream(streamedRes);
    final data = jsonDecode(utf8.decode(res.bodyBytes));

    if (res.statusCode == 200 && data['success'] == true) {
      return DiagnosisResult.fromJson(data);
    } else {
      throw Exception(data['detail'] ?? 'Lỗi suy luận AI trên máy chủ');
    }
  }

  // --- 3. DIAGNOSIS HISTORY & DETAIL ---
  Future<List<DiagnosisHistoryModel>> getDiagnosisHistory({
    int? farmId,
    int? plotId,
    String? cropId,
    int? orgId,
  }) async {
    final queryParams = <String, String>{};
    if (farmId != null) queryParams['farm_id'] = farmId.toString();
    if (plotId != null) queryParams['plot_id'] = plotId.toString();
    if (cropId != null && cropId != 'all') queryParams['crop_id'] = cropId;
    if (orgId != null) queryParams['org_id'] = orgId.toString();

    final uri = Uri.parse('$_baseUrl/api/diagnoses').replace(queryParameters: queryParams.isEmpty ? null : queryParams);
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['diagnoses'] as List? ?? [];
      return list.map((e) => DiagnosisHistoryModel.fromJson(e)).toList();
    }
    return [];
  }

  Future<DiagnosisHistoryModel?> getDiagnosisDetail(int diagId) async {
    final uri = Uri.parse('$_baseUrl/api/diagnoses/$diagId');
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      if (data['diagnosis'] != null) {
        return DiagnosisHistoryModel.fromJson(data['diagnosis']);
      }
    }
    return null;
  }

  Future<bool> linkDiagnosisToFarm(int diagId, int farmId, {int? plotId}) async {
    final uri = Uri.parse('$_baseUrl/api/diagnoses/$diagId/link');
    final payload = {'farm_id': farmId, 'plot_id': ?plotId};
    final res = await http.post(uri, headers: _headers(), body: jsonEncode(payload));
    return res.statusCode == 200;
  }

  // --- 4. CONTEXTUAL AI ASSISTANT ---
  Future<String> askAssistant({
    required String message,
    String? crop,
    String? disease,
    List<Map<String, dynamic>>? history,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/assistant/chat');
    final payload = {
      'message': message,
      'crop': crop,
      'disease': disease,
      'history': history ?? [],
    };
    final res = await http.post(
      uri,
      headers: _headers(),
      body: jsonEncode(payload),
    );
    final data = jsonDecode(utf8.decode(res.bodyBytes));
    if (res.statusCode == 200 && data['success'] == true) {
      return data['response'] ?? data['reply'] ?? '';
    } else {
      throw Exception(data['detail'] ?? 'Trợ lý AI không phản hồi');
    }
  }

  // --- 5. FARMS & PLOTS MANAGEMENT ---
  Future<List<FarmModel>> getFarms() async {
    final uri = Uri.parse('$_baseUrl/api/farms');
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['farms'] as List? ?? [];
      return list.map((e) => FarmModel.fromJson(e)).toList();
    }
    return [];
  }

  Future<FarmModel?> createFarm(Map<String, dynamic> farmData) async {
    final uri = Uri.parse('$_baseUrl/api/farms');
    final res = await http.post(uri, headers: _headers(), body: jsonEncode(farmData));
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      if (data['farm'] != null) {
        return FarmModel.fromJson(data['farm']);
      }
    }
    return null;
  }

  // --- 6. TASKS & CROP CALENDAR ---
  Future<List<TaskModel>> getTasks({
    String? view,
    int? farmId,
    int? plotId,
    String? status,
    String? priority,
  }) async {
    final queryParams = <String, String>{};
    if (view != null) queryParams['view'] = view;
    if (farmId != null) queryParams['farm_id'] = farmId.toString();
    if (plotId != null) queryParams['plot_id'] = plotId.toString();
    if (status != null) queryParams['status'] = status;
    if (priority != null) queryParams['priority'] = priority;

    final uri = Uri.parse('$_baseUrl/api/calendar/tasks').replace(queryParameters: queryParams.isEmpty ? null : queryParams);
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['tasks'] as List? ?? [];
      return list.map((e) => TaskModel.fromJson(e)).toList();
    }
    return [];
  }

  Future<TaskModel?> createTask(Map<String, dynamic> taskPayload) async {
    final uri = Uri.parse('$_baseUrl/api/calendar/tasks');
    final res = await http.post(uri, headers: _headers(), body: jsonEncode(taskPayload));
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      if (data['task'] != null) {
        return TaskModel.fromJson(data['task']);
      }
    }
    return null;
  }

  Future<TaskModel?> createTaskFromDiagnosis({
    required int diagnosisId,
    String? title,
    String? dueDate,
    String? priority,
    String? notes,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/calendar/tasks/from-diagnosis');
    final payload = {
      'diagnosis_id': diagnosisId,
      'title': ?title,
      'due_date': ?dueDate,
      'priority': ?priority,
      'notes': ?notes,
    };
    final res = await http.post(uri, headers: _headers(), body: jsonEncode(payload));
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      if (data['task'] != null) {
        return TaskModel.fromJson(data['task']);
      }
    }
    return null;
  }

  Future<TaskModel?> completeTask(int taskId, {String? notes}) async {
    final uri = Uri.parse('$_baseUrl/api/calendar/tasks/$taskId/complete');
    final res = await http.post(
      uri,
      headers: _headers(),
      body: jsonEncode({'notes': notes ?? 'Hoàn thành từ ứng dụng di động GARI'}),
    );
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      if (data['task'] != null) {
        return TaskModel.fromJson(data['task']);
      }
    }
    return null;
  }

  // --- 7. ORGANIZATIONS & TEAM MANAGEMENT ---
  Future<List<OrganizationModel>> getOrganizations() async {
    final uri = Uri.parse('$_baseUrl/api/organizations');
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['organizations'] as List? ?? [];
      return list.map((e) => OrganizationModel.fromJson(e)).toList();
    }
    return [];
  }

  Future<List<Map<String, dynamic>>> getOrganizationMembers(int orgId) async {
    final uri = Uri.parse('$_baseUrl/api/organizations/$orgId/members');
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['members'] as List? ?? [];
      return list.map((e) => Map<String, dynamic>.from(e)).toList();
    }
    return [];
  }

  // --- 8. COMMUNITY & KNOWLEDGE LIBRARY ---
  Future<List<KnowledgeArticleModel>> getKnowledgeArticles({
    String? cropId,
    String? category,
    String? search,
  }) async {
    final queryParams = <String, String>{};
    if (cropId != null && cropId != 'all') queryParams['crop_id'] = cropId;
    if (category != null && category.isNotEmpty) queryParams['category'] = category;
    if (search != null && search.isNotEmpty) queryParams['q'] = search;

    final uri = Uri.parse('$_baseUrl/api/knowledge/articles').replace(
      queryParameters: queryParams.isEmpty ? null : queryParams,
    );
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['articles'] as List? ?? [];
      return list.map((e) => KnowledgeArticleModel.fromJson(e)).toList();
    }
    return [];
  }

  Future<KnowledgeArticleModel?> getKnowledgeArticle(String idOrSlug) async {
    final uri = Uri.parse('$_baseUrl/api/knowledge/articles/$idOrSlug');
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      if (data['article'] != null) {
        return KnowledgeArticleModel.fromJson(data['article']);
      }
    }
    return null;
  }

  Future<List<CommunityPostModel>> getCommunityPosts({
    String? cropId,
    int limit = 20,
    int offset = 0,
  }) async {
    final queryParams = <String, String>{
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    if (cropId != null && cropId != 'all') queryParams['crop_id'] = cropId;

    final uri = Uri.parse('$_baseUrl/api/community/posts').replace(queryParameters: queryParams);
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['posts'] as List? ?? [];
      return list.map((e) => CommunityPostModel.fromJson(e)).toList();
    }
    return [];
  }

  Future<CommunityPostModel?> createCommunityPost({
    required String title,
    required String content,
    required String cropId,
    String? region,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/community/posts');
    final payload = {
      'title': title,
      'content': content,
      'crop_id': cropId,
      'region': ?region,
    };
    final res = await http.post(uri, headers: _headers(), body: jsonEncode(payload));
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      if (data['post'] != null) {
        return CommunityPostModel.fromJson(data['post']);
      }
    }
    return null;
  }

  Future<bool> togglePostLike(int postId) async {
    final uri = Uri.parse('$_baseUrl/api/community/posts/$postId/like');
    final res = await http.post(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      return data['liked'] == true;
    }
    return false;
  }

  // --- 9. EXPERT CONSULTATION ---
  Future<Map<String, dynamic>?> createExpertConsultation({
    required int diagnosisId,
    required String description,
    bool consentShareFarm = true,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/expert/cases');
    final payload = {
      'diagnosis_id': diagnosisId,
      'symptoms_description': description,
      'notes': description,
      'consent_share_farm_data': consentShareFarm,
    };
    final res = await http.post(uri, headers: _headers(), body: jsonEncode(payload));
    if (res.statusCode == 200) {
      return jsonDecode(utf8.decode(res.bodyBytes));
    }
    return null;
  }

  Future<List<Map<String, dynamic>>> getExpertCases({String filter = 'all'}) async {
    final path = (_currentUser != null && _currentUser!.isExpert)
        ? '$_baseUrl/api/expert/portal/cases?filter_type=$filter'
        : '$_baseUrl/api/expert/cases';
    final uri = Uri.parse(path);
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['cases'] as List? ?? [];
      return list.map((e) => Map<String, dynamic>.from(e)).toList();
    }
    return [];
  }

  Future<List<ChatMessage>> getCaseMessages(int caseId) async {
    final uri = Uri.parse('$_baseUrl/api/expert/cases/$caseId/messages');
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['messages'] as List? ?? [];
      return list.map((e) => ChatMessage.fromJson(e)).toList();
    }
    return [];
  }

  Future<void> sendCaseMessage(int caseId, String text) async {
    final uri = Uri.parse('$_baseUrl/api/expert/cases/$caseId/messages');
    await http.post(
      uri,
      headers: _headers(),
      body: jsonEncode({'message': text}),
    );
  }

  // --- 10. NOTIFICATIONS ---
  Future<List<NotificationModel>> getNotifications() async {
    final uri = Uri.parse('$_baseUrl/api/notifications');
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      final list = data['notifications'] as List? ?? [];
      return list.map((e) => NotificationModel.fromJson(e)).toList();
    }
    return [];
  }

  Future<void> markNotificationRead(int notifId) async {
    final uri = Uri.parse('$_baseUrl/api/notifications/$notifId/read');
    await http.patch(uri, headers: _headers());
  }

  // --- 11. SUBSCRIPTION & USAGE ---
  Future<SubscriptionUsageModel?> getSubscriptionUsage({int? orgId}) async {
    final queryParams = <String, String>{};
    if (orgId != null) queryParams['org_id'] = orgId.toString();

    final uri = Uri.parse('$_baseUrl/api/subscriptions/usage').replace(
      queryParameters: queryParams.isEmpty ? null : queryParams,
    );
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      return SubscriptionUsageModel.fromJson(data);
    }
    return null;
  }
}
