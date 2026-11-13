import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/app_theme.dart';
import '../models/notification_model.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final ApiClient _api = ApiClient();
  List<NotificationModel> _notifications = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadNotifications();
  }

  Future<void> _loadNotifications() async {
    setState(() => _isLoading = true);
    final list = await _api.getNotifications();
    setState(() {
      _notifications = list;
      _isLoading = false;
    });
  }

  Future<void> _markRead(NotificationModel notif) async {
    await _api.markNotificationRead(notif.id);
    _loadNotifications();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Thông Báo & Cảnh Báo'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadNotifications,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.primaryGreen))
          : _notifications.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: const [
                      Icon(Icons.notifications_none, size: 56, color: Colors.grey),
                      SizedBox(height: 12),
                      Text('Bạn chưa có thông báo mới.', style: TextStyle(color: Colors.grey, fontSize: 15)),
                    ],
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: _notifications.length,
                  separatorBuilder: (_, index) => const SizedBox(height: 10),
                  itemBuilder: (context, idx) {
                    final n = _notifications[idx];
                    return Card(
                      color: n.isRead ? Colors.white : const Color(0xFFF0FDF4),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: n.isRead ? const Color(0xFFE2E8F0) : const Color(0xFFD1FAE5),
                          child: Icon(
                            n.type == 'expert' ? Icons.medical_services : Icons.notifications,
                            color: n.isRead ? Colors.grey : AppTheme.primaryGreen,
                          ),
                        ),
                        title: Text(
                          n.title,
                          style: TextStyle(
                            fontWeight: n.isRead ? FontWeight.w500 : FontWeight.w700,
                          ),
                        ),
                        subtitle: Text(n.message),
                        trailing: n.isRead
                            ? null
                            : IconButton(
                                icon: const Icon(Icons.check, size: 18, color: AppTheme.primaryGreen),
                                onPressed: () => _markRead(n),
                              ),
                      ),
                    );
                  },
                ),
    );
  }
}
