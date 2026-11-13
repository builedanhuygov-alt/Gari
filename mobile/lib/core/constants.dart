class CropItem {
  final String id;
  final String nameVi;
  final String nameEn;
  final String icon;

  const CropItem({
    required this.id,
    required this.nameVi,
    required this.nameEn,
    required this.icon,
  });
}

class AppConstants {
  static const String appName = 'GARI • Trợ lý nông nghiệp AI';
  static const String appVersion = '2.6.0';

  // Default server URL - Production Vercel / Cloud Gateway
  static const String defaultBaseUrl = 'https://api.gari.vn';
  static const String androidEmulatorBaseUrl = 'http://10.0.2.2:8000';
  static const String localDevBaseUrl = 'http://127.0.0.1:8000';

  // Storage Keys
  static const String tokenKey = 'gari_auth_token';
  static const String userKey = 'gari_user_profile';
  static const String serverUrlKey = 'gari_server_url';
  static const String offlineCasesKey = 'gari_offline_cases';

  // The 7 Primary Crops supported by GARI Core Engine
  static const List<CropItem> primaryCrops = [
    CropItem(id: 'all', nameVi: 'Tự động nhận diện', nameEn: 'Auto Detect', icon: '🌿'),
    CropItem(id: 'coffee', nameVi: 'Cà phê', nameEn: 'Coffee', icon: '☕'),
    CropItem(id: 'pepper', nameVi: 'Hồ tiêu', nameEn: 'Black Pepper', icon: '🌱'),
    CropItem(id: 'rice', nameVi: 'Lúa', nameEn: 'Rice', icon: '🌾'),
    CropItem(id: 'durian', nameVi: 'Sầu riêng', nameEn: 'Durian', icon: '🍈'),
    CropItem(id: 'tomato', nameVi: 'Cà chua', nameEn: 'Tomato', icon: '🍅'),
    CropItem(id: 'chili', nameVi: 'Ớt', nameEn: 'Chili', icon: '🌶️'),
    CropItem(id: 'corn', nameVi: 'Bắp / Ngô', nameEn: 'Corn', icon: '🌽'),
  ];

  static const List<String> supportedCrops = [
    'Tự động nhận diện',
    'Cà phê',
    'Hồ tiêu',
    'Lúa',
    'Sầu riêng',
    'Cà chua',
    'Ớt',
    'Bắp / Ngô',
  ];
}
