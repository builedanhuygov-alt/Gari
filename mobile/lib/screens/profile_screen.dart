import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/app_theme.dart';
import '../core/constants.dart';
import '../models/subscription_usage_model.dart';
import '../models/diagnosis_history_model.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _serverUrlCtrl = TextEditingController();

  SubscriptionUsageModel? _usage;
  bool _isLoadingUsage = false;

  List<DiagnosisHistoryModel> _history = [];
  bool _isLoadingHistory = false;

  @override
  void initState() {
    super.initState();
    _serverUrlCtrl.text = _api.baseUrl;
    if (_api.isAuthenticated) {
      _loadUsage();
      _loadHistory();
    }
  }

  Future<void> _loadUsage() async {
    setState(() => _isLoadingUsage = true);
    final usage = await _api.getSubscriptionUsage();
    if (mounted) {
      setState(() {
        _usage = usage;
        _isLoadingUsage = false;
      });
    }
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoadingHistory = true);
    final history = await _api.getDiagnosisHistory();
    if (mounted) {
      setState(() {
        _history = history;
        _isLoadingHistory = false;
      });
    }
  }

  void _showLoginDialog() {
    final emailCtrl = TextEditingController(text: 'farmer_demo@gari.vn');
    final passCtrl = TextEditingController(text: 'Farmer@123456');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Đăng Nhập GARI Nông Hộ'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: emailCtrl,
              decoration: const InputDecoration(labelText: 'Email tài khoản'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: passCtrl,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Mật khẩu'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Hủy')),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(ctx);
              final res = await _api.login(emailCtrl.text.trim(), passCtrl.text);
              if (res['success'] == true) {
                setState(() {});
                _loadUsage();
                _loadHistory();
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Đăng nhập thành công!')),
                  );
                }
              } else {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(res['message'] ?? 'Thất bại')),
                  );
                }
              }
            },
            child: const Text('Đăng Nhập'),
          ),
        ],
      ),
    );
  }

  void _showRegisterDialog() {
    final nameCtrl = TextEditingController();
    final emailCtrl = TextEditingController();
    final passCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Đăng Ký Tài Khoản GARI'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Họ và tên nông hộ')),
            const SizedBox(height: 10),
            TextField(controller: emailCtrl, decoration: const InputDecoration(labelText: 'Email')),
            const SizedBox(height: 10),
            TextField(controller: passCtrl, obscureText: true, decoration: const InputDecoration(labelText: 'Mật khẩu')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Hủy')),
          ElevatedButton(
            onPressed: () async {
              if (nameCtrl.text.isEmpty || emailCtrl.text.isEmpty || passCtrl.text.isEmpty) return;
              Navigator.pop(ctx);
              final res = await _api.register(
                email: emailCtrl.text.trim(),
                password: passCtrl.text,
                fullName: nameCtrl.text.trim(),
              );
              if (res['success'] == true) {
                setState(() {});
                _loadUsage();
                _loadHistory();
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Đăng ký tài khoản thành công!')),
                  );
                }
              } else {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(res['message'] ?? 'Đăng ký thất bại')),
                  );
                }
              }
            },
            child: const Text('Tạo Tài Khoản'),
          ),
        ],
      ),
    );
  }

  void _saveServerUrl() async {
    await _api.setBaseUrl(_serverUrlCtrl.text);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã cập nhật máy chủ kết nối!')),
      );
    }
  }

  void _viewDiagnosisModal(DiagnosisHistoryModel d) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(d.diseaseNameVi),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Cây trồng: ${d.cropName} (${d.cropId})'),
            const SizedBox(height: 6),
            Text('Độ tin cậy: ${d.confidencePercent.toStringAsFixed(1)}%'),
            const SizedBox(height: 6),
            Text('Mức nghiêm trọng: ${d.severity}'),
            const SizedBox(height: 6),
            Text('Thời gian chẩn đoán: ${d.createdAt}'),
            if (d.farmName != null) ...[
              const SizedBox(height: 6),
              Text('Vườn liên kết: ${d.farmName}'),
            ],
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Đóng')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = _api.currentUser;
    final isAuth = _api.isAuthenticated;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Tài Khoản & Cài Đặt'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // User Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 36,
                    backgroundColor: AppTheme.primaryGreen.withAlpha(30),
                    child: Text(
                      isAuth ? (user?.fullName.characters.first ?? 'G') : '?',
                      style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: AppTheme.primaryGreen),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    isAuth ? (user?.fullName ?? 'Người dùng') : 'Chưa Đăng Nhập',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isAuth ? (user?.email ?? '') : 'Đăng nhập để đồng bộ lịch sử chẩn đoán & nông trại',
                    style: const TextStyle(color: Colors.grey, fontSize: 13),
                  ),
                  const SizedBox(height: 16),

                  if (isAuth) ...[
                    Wrap(
                      spacing: 8,
                      children: [
                        Chip(
                          avatar: const Icon(Icons.star, size: 16, color: Colors.amber),
                          label: Text('Gói: ${(user?.accountType ?? "Free").toUpperCase()}'),
                        ),
                        if (user?.isExpert == true)
                          const Chip(
                            avatar: Icon(Icons.verified, size: 16, color: AppTheme.primaryGreen),
                            label: Text('Chuyên Gia BVTV'),
                          ),
                        if (user?.isHostAdmin == true)
                          const Chip(
                            avatar: Icon(Icons.admin_panel_settings, size: 16, color: Colors.blue),
                            label: Text('Host Admin'),
                          ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      icon: const Icon(Icons.logout, color: AppTheme.accentRed),
                      label: const Text('Đăng Xuất Khỏi Thiết Bị', style: TextStyle(color: AppTheme.accentRed)),
                      onPressed: () async {
                        await _api.logout();
                        setState(() {
                          _usage = null;
                          _history = [];
                        });
                      },
                    ),
                  ] else ...[
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            icon: const Icon(Icons.login),
                            label: const Text('Đăng Nhập'),
                            onPressed: _showLoginDialog,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            icon: const Icon(Icons.person_add),
                            label: const Text('Đăng Ký'),
                            onPressed: _showRegisterDialog,
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),

          // SUBSCRIPTION & 7-DIMENSION USAGE DASHBOARD
          if (isAuth) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.speed, color: AppTheme.primaryGreen),
                            const SizedBox(width: 8),
                            const Text('Định Mức Sử Dụng (7 Tiêu Chí)', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                          ],
                        ),
                        if (_usage != null)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(color: AppTheme.primaryLight.withAlpha(50), borderRadius: BorderRadius.circular(12)),
                            child: Text(_usage!.planName, style: const TextStyle(color: AppTheme.primaryGreen, fontWeight: FontWeight.bold, fontSize: 11)),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    if (_isLoadingUsage)
                      const Center(child: Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator(color: AppTheme.primaryGreen)))
                    else if (_usage == null || _usage!.metrics.isEmpty)
                      const Text('Đang làm mới định mức tài khoản...', style: TextStyle(color: Colors.grey, fontSize: 13))
                    else ...[
                      ..._usage!.metrics.values.map((dim) {
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(dim.label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                                  Text(
                                    dim.isUnlimited
                                        ? 'Đã dùng ${dim.used} ${dim.unit} (Không giới hạn)'
                                        : '${dim.used} / ${dim.limit} ${dim.unit} (${dim.percentage.toStringAsFixed(0)}%)',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: dim.isExhausted ? AppTheme.accentRed : Colors.grey[700],
                                      fontWeight: dim.isExhausted ? FontWeight.bold : FontWeight.normal,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(4),
                                child: LinearProgressIndicator(
                                  value: dim.isUnlimited ? 0.2 : (dim.percentage / 100.0).clamp(0.0, 1.0),
                                  backgroundColor: Colors.grey[200],
                                  color: dim.isExhausted
                                      ? AppTheme.accentRed
                                      : (dim.percentage >= 80.0 ? AppTheme.accentAmber : AppTheme.primaryGreen),
                                  minHeight: 6,
                                ),
                              ),
                            ],
                          ),
                        );
                      }),
                      if (_usage!.needsUpgrade) ...[
                        const SizedBox(height: 8),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFFFBEB),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: const Color(0xFFFDE68A)),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.info_outline, color: AppTheme.accentAmber, size: 20),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Gợi ý nâng cấp: ${_usage!.suggestedPlanName ?? "Gói Pro"} để mở rộng định mức canh tác.',
                                  style: const TextStyle(fontSize: 12, color: Color(0xFF92400E)),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),

            // DIAGNOSIS HISTORY SECTION
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.history, color: AppTheme.primaryGreen),
                            const SizedBox(width: 8),
                            const Text('Lịch Sử Chẩn Đoán', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                          ],
                        ),
                        IconButton(
                          icon: const Icon(Icons.refresh, size: 20),
                          onPressed: _loadHistory,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),

                    if (_isLoadingHistory)
                      const Center(child: Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator(color: AppTheme.primaryGreen)))
                    else if (_history.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 16),
                        child: Center(
                          child: Text('Chưa có lịch sử chẩn đoán lá nào.', style: TextStyle(color: Colors.grey)),
                        ),
                      )
                    else
                      ..._history.take(5).map((diag) => ListTile(
                            dense: true,
                            contentPadding: EdgeInsets.zero,
                            leading: CircleAvatar(
                              backgroundColor: diag.isHealthy ? AppTheme.primaryGreen.withAlpha(30) : AppTheme.accentAmber.withAlpha(30),
                              child: Icon(
                                diag.isHealthy ? Icons.eco : Icons.bug_report,
                                color: diag.isHealthy ? AppTheme.primaryGreen : AppTheme.accentAmber,
                                size: 18,
                              ),
                            ),
                            title: Text(diag.diseaseNameVi, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13.5)),
                            subtitle: Text('${diag.cropName} • ${(diag.confidencePercent).toStringAsFixed(1)}% tin cậy'),
                            trailing: const Icon(Icons.chevron_right, size: 18, color: Colors.grey),
                            onTap: () => _viewDiagnosisModal(diag),
                          )),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),
          ],

          // Server Connection Config Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Cấu Hình Kết Nối Backend API', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                  const SizedBox(height: 6),
                  const Text('Chọn địa chỉ máy chủ API GARI phục vụ suy luận mô hình và đồng bộ dữ liệu.', style: TextStyle(color: Colors.grey, fontSize: 12.5)),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _serverUrlCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Server Base URL',
                      isDense: true,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      TextButton(
                        onPressed: () {
                          _serverUrlCtrl.text = AppConstants.defaultBaseUrl;
                          _saveServerUrl();
                        },
                        child: const Text('Localhost (8000)'),
                      ),
                      TextButton(
                        onPressed: () {
                          _serverUrlCtrl.text = AppConstants.androidEmulatorBaseUrl;
                          _saveServerUrl();
                        },
                        child: const Text('Android (10.0.2.2)'),
                      ),
                      const Spacer(),
                      ElevatedButton(
                        onPressed: _saveServerUrl,
                        child: const Text('Lưu'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),

          // About app
          const Center(
            child: Text(
              '${AppConstants.appName} • Phiên bản ${AppConstants.appVersion}\nBản quyền thuộc về GARI AgriTech AI Lab',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}
