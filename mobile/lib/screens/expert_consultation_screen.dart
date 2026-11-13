import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/app_theme.dart';
import '../models/chat_message.dart';

class ExpertConsultationScreen extends StatefulWidget {
  const ExpertConsultationScreen({super.key});

  @override
  State<ExpertConsultationScreen> createState() => _ExpertConsultationScreenState();
}

class _ExpertConsultationScreenState extends State<ExpertConsultationScreen> {
  final ApiClient _api = ApiClient();
  List<Map<String, dynamic>> _cases = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadCases();
  }

  Future<void> _loadCases() async {
    setState(() => _isLoading = true);
    final cases = await _api.getExpertCases();
    setState(() {
      _cases = cases;
      _isLoading = false;
    });
  }

  void _openCaseThread(Map<String, dynamic> c) {
    final caseId = c['id'] is int ? c['id'] : int.tryParse(c['id'].toString()) ?? 0;
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CaseChatScreen(
          caseId: caseId,
          crop: c['crop'] ?? 'Cây trồng',
          disease: c['ai_disease_predicted'] ?? 'Ca tư vấn',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isExpert = _api.currentUser?.isExpert == true;

    return Scaffold(
      appBar: AppBar(
        title: Text(isExpert ? 'Cổng Chuyên Gia GARI' : 'Tư Vấn Chuyên Gia BVTV'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadCases,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.primaryGreen))
          : RefreshIndicator(
              onRefresh: _loadCases,
              color: AppTheme.primaryGreen,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Card(
                    color: const Color(0xFFF0FDF4),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: [
                          const Icon(Icons.verified_user, color: AppTheme.primaryGreen, size: 36),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  isExpert ? 'Chế độ Bác sĩ Cây trồng' : 'Hội đồng Chuyên gia BVTV',
                                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  isExpert
                                      ? 'Tiếp nhận ca bệnh, gửi trao đổi trực tiếp và ký duyệt phác đồ điều trị an toàn cho nông hộ.'
                                      : 'Được hỗ trợ trực tiếp bởi các kỹ sư nông học và viện BVTV đối tác.',
                                  style: const TextStyle(fontSize: 12.5, color: Color(0xFF166534)),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Danh Sách Ca Tư Vấn', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                      Text('${_cases.length} ca', style: const TextStyle(color: Colors.grey)),
                    ],
                  ),
                  const SizedBox(height: 12),

                  if (_cases.isEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(32),
                        child: Column(
                          children: const [
                            Icon(Icons.inbox_outlined, size: 48, color: Colors.grey),
                            SizedBox(height: 12),
                            Text('Hiện chưa có ca tham vấn nào.', style: TextStyle(color: Colors.grey)),
                          ],
                        ),
                      ),
                    )
                  else
                    ..._cases.map((c) {
                      final status = c['status'] ?? 'Pending';
                      final isResolved = status == 'Resolved' || status == 'Đã tư vấn';
                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: ListTile(
                          onTap: () => _openCaseThread(c),
                          leading: CircleAvatar(
                            backgroundColor: isResolved ? const Color(0xFFD1FAE5) : const Color(0xFFFEF3C7),
                            child: Icon(
                              isResolved ? Icons.check_circle : Icons.hourglass_top,
                              color: isResolved ? AppTheme.primaryGreen : AppTheme.accentAmber,
                            ),
                          ),
                          title: Text(
                            '${c['crop'] ?? 'Cây trồng'} - ${c['ai_disease_predicted'] ?? 'Cần tư vấn'}',
                            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
                          ),
                          subtitle: Text('Trạng thái: $status • Mã #${c['id']}'),
                          trailing: const Icon(Icons.chat_bubble_outline, color: AppTheme.primaryGreen),
                        ),
                      );
                    }),
                ],
              ),
            ),
    );
  }
}

class CaseChatScreen extends StatefulWidget {
  final int caseId;
  final String crop;
  final String disease;

  const CaseChatScreen({
    super.key,
    required this.caseId,
    required this.crop,
    required this.disease,
  });

  @override
  State<CaseChatScreen> createState() => _CaseChatScreenState();
}

class _CaseChatScreenState extends State<CaseChatScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _textCtrl = TextEditingController();
  List<ChatMessage> _messages = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadMessages();
  }

  Future<void> _loadMessages() async {
    setState(() => _isLoading = true);
    final msgs = await _api.getCaseMessages(widget.caseId);
    setState(() {
      _messages = msgs;
      _isLoading = false;
    });
  }

  Future<void> _sendMessage() async {
    final text = _textCtrl.text.trim();
    if (text.isEmpty) return;
    _textCtrl.clear();
    await _api.sendCaseMessage(widget.caseId, text);
    _loadMessages();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.crop}: ${widget.disease}'),
      ),
      body: Column(
        children: [
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: AppTheme.primaryGreen))
                : _messages.isEmpty
                    ? const Center(
                        child: Text('Chưa có tin nhắn trong ca bệnh này.', style: TextStyle(color: Colors.grey)),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _messages.length,
                        itemBuilder: (context, idx) {
                          final m = _messages[idx];
                          return Align(
                            alignment: m.isUser ? Alignment.centerRight : Alignment.centerLeft,
                            child: Container(
                              margin: const EdgeInsets.only(bottom: 10),
                              padding: const EdgeInsets.all(12),
                              constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
                              decoration: BoxDecoration(
                                color: m.isUser ? AppTheme.primaryGreen : Colors.white,
                                borderRadius: BorderRadius.circular(12),
                                border: m.isUser ? null : Border.all(color: const Color(0xFFE2E8F0)),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (m.isPrescription)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                      margin: const EdgeInsets.only(bottom: 4),
                                      decoration: BoxDecoration(
                                        color: Colors.amber.shade100,
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: const Text('📜 PHÁC ĐỒ ĐIỀU TRỊ', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Colors.orange)),
                                    ),
                                  Text(
                                    m.text,
                                    style: TextStyle(color: m.isUser ? Colors.white : Colors.black87),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),
          Container(
            padding: const EdgeInsets.all(12),
            color: Colors.white,
            child: SafeArea(
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _textCtrl,
                      decoration: const InputDecoration(hintText: 'Nhập tin nhắn...'),
                      onSubmitted: (_) => _sendMessage(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.send, color: AppTheme.primaryGreen),
                    onPressed: _sendMessage,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
