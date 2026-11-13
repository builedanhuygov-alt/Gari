import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/app_theme.dart';
import '../models/farm_model.dart';
import '../models/task_model.dart';
import '../models/organization_model.dart';

class FarmsScreen extends StatefulWidget {
  const FarmsScreen({super.key});

  @override
  State<FarmsScreen> createState() => _FarmsScreenState();
}

class _FarmsScreenState extends State<FarmsScreen> with SingleTickerProviderStateMixin {
  final ApiClient _api = ApiClient();
  late TabController _tabController;

  // Farms state
  List<FarmModel> _farms = [];
  bool _isLoadingFarms = true;

  // Tasks state
  List<TaskModel> _tasks = [];
  bool _isLoadingTasks = true;
  String _taskFilter = 'all'; // all, today, upcoming, overdue, completed

  // Organization state
  List<OrganizationModel> _organizations = [];
  OrganizationModel? _selectedOrg;
  List<Map<String, dynamic>> _orgMembers = [];
  bool _isLoadingOrgs = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadAllData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAllData() async {
    await Future.wait([
      _loadFarms(),
      _loadTasks(),
      _loadOrganizations(),
    ]);
  }

  Future<void> _loadFarms() async {
    setState(() => _isLoadingFarms = true);
    final farms = await _api.getFarms();
    if (mounted) {
      setState(() {
        _farms = farms;
        _isLoadingFarms = false;
      });
    }
  }

  Future<void> _loadTasks() async {
    setState(() => _isLoadingTasks = true);
    final viewParam = (_taskFilter == 'all' || _taskFilter == 'completed') ? null : _taskFilter;
    final statusParam = _taskFilter == 'completed' ? 'completed' : null;
    final tasks = await _api.getTasks(view: viewParam, status: statusParam);
    if (mounted) {
      setState(() {
        _tasks = tasks;
        _isLoadingTasks = false;
      });
    }
  }

  Future<void> _loadOrganizations() async {
    setState(() => _isLoadingOrgs = true);
    final orgs = await _api.getOrganizations();
    if (mounted) {
      setState(() {
        _organizations = orgs;
        if (orgs.isNotEmpty && _selectedOrg == null) {
          _selectedOrg = orgs.first;
        }
        _isLoadingOrgs = false;
      });
      if (_selectedOrg != null) {
        _loadOrgMembers(_selectedOrg!.id);
      }
    }
  }

  Future<void> _loadOrgMembers(int orgId) async {
    final members = await _api.getOrganizationMembers(orgId);
    if (mounted) {
      setState(() {
        _orgMembers = members;
      });
    }
  }

  void _showCreateTaskDialog() {
    final titleCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    String priority = 'MEDIUM';
    int? selectedFarmId = _farms.isNotEmpty ? _farms.first.id : null;
    DateTime dueDate = DateTime.now().add(const Duration(days: 1));

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) => Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
            left: 20,
            right: 20,
            top: 20,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Tạo Công Việc Canh Tác', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(ctx)),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: titleCtrl,
                decoration: const InputDecoration(labelText: 'Tên nhiệm vụ / công việc', isDense: true),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: descCtrl,
                maxLines: 2,
                decoration: const InputDecoration(labelText: 'Ghi chú kỹ thuật canh tác', isDense: true),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  const Text('Mức ưu tiên: '),
                  const SizedBox(width: 8),
                  DropdownButton<String>(
                    value: priority,
                    items: const [
                      DropdownMenuItem(value: 'LOW', child: Text('Thấp')),
                      DropdownMenuItem(value: 'MEDIUM', child: Text('Bình thường')),
                      DropdownMenuItem(value: 'HIGH', child: Text('Cao')),
                      DropdownMenuItem(value: 'URGENT', child: Text('Khẩn cấp')),
                    ],
                    onChanged: (val) {
                      if (val != null) setSheetState(() => priority = val);
                    },
                  ),
                ],
              ),
              if (_farms.isNotEmpty) ...[
                const SizedBox(height: 10),
                Row(
                  children: [
                    const Text('Vườn áp dụng: '),
                    const SizedBox(width: 8),
                    Expanded(
                      child: DropdownButton<int>(
                        value: selectedFarmId,
                        isExpanded: true,
                        items: _farms.map((f) {
                          return DropdownMenuItem<int>(value: f.id, child: Text(f.name));
                        }).toList(),
                        onChanged: (val) {
                          if (val != null) setSheetState(() => selectedFarmId = val);
                        },
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 16),
              ElevatedButton.icon(
                icon: const Icon(Icons.check),
                label: const Text('Lưu Công Việc'),
                onPressed: () async {
                  if (titleCtrl.text.trim().isEmpty) return;
                  Navigator.pop(ctx);
                  final task = await _api.createTask({
                    'title': titleCtrl.text.trim(),
                    'description': descCtrl.text.trim(),
                    'priority': priority,
                    'due_date': dueDate.toIso8601String().split('T').first,
                    'farm_id': ?selectedFarmId,
                  });
                  if (task != null) {
                    _loadTasks();
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Đã thêm công việc vào Lịch canh tác!')),
                      );
                    }
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Vườn & Canh Tác'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.checklist), text: 'Lịch Việc'),
            Tab(icon: Icon(Icons.yard), text: 'Nông Trại'),
            Tab(icon: Icon(Icons.corporate_fare), text: 'Hợp Tác Xã'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          // TAB 1: TASKS & CROP CALENDAR
          RefreshIndicator(
            onRefresh: _loadTasks,
            color: AppTheme.primaryGreen,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Filter chips
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      ('all', 'Tất cả'),
                      ('today', 'Hôm nay'),
                      ('upcoming', 'Sắp tới'),
                      ('overdue', 'Quá hạn'),
                      ('completed', 'Đã xong'),
                    ].map((entry) {
                      final isSelected = _taskFilter == entry.$1;
                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: FilterChip(
                          label: Text(entry.$2),
                          selected: isSelected,
                          onSelected: (val) {
                            setState(() => _taskFilter = entry.$1);
                            _loadTasks();
                          },
                        ),
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 16),

                if (_isLoadingTasks)
                  const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator(color: AppTheme.primaryGreen)))
                else if (_tasks.isEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        children: const [
                          Icon(Icons.task_alt, size: 48, color: Colors.grey),
                          SizedBox(height: 12),
                          Text('Không có nhiệm vụ nào trong danh mục này.', style: TextStyle(color: Colors.grey)),
                        ],
                      ),
                    ),
                  )
                else
                  ..._tasks.map((task) {
                    Color priorityColor = Colors.grey;
                    if (task.priority == 'HIGH') priorityColor = AppTheme.accentAmber;
                    if (task.priority == 'URGENT') priorityColor = AppTheme.accentRed;
                    if (task.priority == 'LOW') priorityColor = Colors.blueGrey;

                    return Card(
                      margin: const EdgeInsets.only(bottom: 10),
                      child: ListTile(
                        leading: IconButton(
                          icon: Icon(
                            task.isCompleted ? Icons.check_circle : Icons.radio_button_unchecked,
                            color: task.isCompleted ? AppTheme.primaryGreen : Colors.grey,
                            size: 26,
                          ),
                          onPressed: () async {
                            if (!task.isCompleted) {
                              await _api.completeTask(task.id);
                              _loadTasks();
                            }
                          },
                        ),
                        title: Text(
                          task.title,
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            decoration: task.isCompleted ? TextDecoration.lineThrough : null,
                            color: task.isCompleted ? Colors.grey : Colors.black87,
                          ),
                        ),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (task.description != null && task.description!.isNotEmpty)
                              Text(task.description!, maxLines: 1, overflow: TextOverflow.ellipsis),
                            const SizedBox(height: 4),
                            Row(
                              children: [
                                if (task.dueDate != null)
                                  Text('Hạn: ${task.dueDate}', style: TextStyle(fontSize: 12, color: task.isOverdue ? AppTheme.accentRed : Colors.grey)),
                                const Spacer(),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(color: priorityColor.withAlpha(30), borderRadius: BorderRadius.circular(4)),
                                  child: Text(task.priority, style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: priorityColor)),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  }),
              ],
            ),
          ),

          // TAB 2: FARMS & PLOTS
          RefreshIndicator(
            onRefresh: _loadFarms,
            color: AppTheme.primaryGreen,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_isLoadingFarms)
                  const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator(color: AppTheme.primaryGreen)))
                else if (_farms.isEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        children: const [
                          Icon(Icons.landscape_outlined, size: 48, color: Colors.grey),
                          SizedBox(height: 12),
                          Text('Chưa có vườn trồng nào được liên kết.', style: TextStyle(color: Colors.grey)),
                        ],
                      ),
                    ),
                  )
                else
                  ..._farms.map((f) => Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor: AppTheme.primaryGreen.withAlpha(30),
                            child: const Icon(Icons.yard, color: AppTheme.primaryGreen),
                          ),
                          title: Text(f.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                          subtitle: Text(
                            '${f.province ?? "Toàn quốc"} • ${f.primaryCrop ?? "Đa cây trồng"} ${f.areaHectares != null ? "• ${f.areaHectares} ha" : ""}',
                          ),
                          trailing: const Icon(Icons.chevron_right, color: Colors.grey),
                        ),
                      )),
              ],
            ),
          ),

          // TAB 3: ORGANIZATIONS & TEAMS
          RefreshIndicator(
            onRefresh: _loadOrganizations,
            color: AppTheme.primaryGreen,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_isLoadingOrgs)
                  const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator(color: AppTheme.primaryGreen)))
                else if (_organizations.isEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        children: const [
                          Icon(Icons.corporate_fare_outlined, size: 48, color: Colors.grey),
                          SizedBox(height: 12),
                          Text('Bạn đang hoạt động ở chế độ Nông hộ độc lập.\nChưa gia nhập Hợp tác xã hoặc Doanh nghiệp nông nghiệp.', textAlign: TextAlign.center, style: TextStyle(color: Colors.grey)),
                        ],
                      ),
                    ),
                  )
                else ...[
                  // Organization selector dropdown
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      child: Row(
                        children: [
                          const Icon(Icons.business, color: AppTheme.primaryGreen),
                          const SizedBox(width: 12),
                          const Text('HTX / DN: ', style: TextStyle(fontWeight: FontWeight.bold)),
                          const SizedBox(width: 8),
                          Expanded(
                            child: DropdownButtonHideUnderline(
                              child: DropdownButton<OrganizationModel>(
                                value: _selectedOrg,
                                isExpanded: true,
                                items: _organizations.map((org) {
                                  return DropdownMenuItem(value: org, child: Text(org.name));
                                }).toList(),
                                onChanged: (val) {
                                  if (val != null) {
                                    setState(() => _selectedOrg = val);
                                    _loadOrgMembers(val.id);
                                  }
                                },
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  if (_selectedOrg != null) ...[
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(_selectedOrg!.name, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                            const SizedBox(height: 4),
                            Text('Loại hình: ${_selectedOrg!.orgType.toUpperCase()} • Quyền của bạn: ${_selectedOrg!.userRole.toUpperCase()}', style: const TextStyle(color: Colors.grey, fontSize: 13)),
                            const Divider(height: 20),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceAround,
                              children: [
                                Column(
                                  children: [
                                    Text('${_selectedOrg!.memberCount}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.primaryGreen)),
                                    const Text('Thành viên', style: TextStyle(fontSize: 12, color: Colors.grey)),
                                  ],
                                ),
                                Column(
                                  children: [
                                    Text('${_selectedOrg!.farmsCount}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.primaryGreen)),
                                    const Text('Vườn liên kết', style: TextStyle(fontSize: 12, color: Colors.grey)),
                                  ],
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text('Danh Sách Thành Viên Đội Ngũ', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    ..._orgMembers.map((m) => Card(
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: Colors.grey.withAlpha(30),
                              child: Text(m['full_name'] != null ? (m['full_name'] as String).characters.first : 'U'),
                            ),
                            title: Text(m['full_name'] ?? m['email'] ?? 'Thành viên', style: const TextStyle(fontWeight: FontWeight.bold)),
                            subtitle: Text(m['email'] ?? ''),
                            trailing: Chip(
                              label: Text((m['role'] ?? 'member').toString().toUpperCase(), style: const TextStyle(fontSize: 11)),
                              backgroundColor: AppTheme.primaryLight.withAlpha(40),
                            ),
                          ),
                        )),
                  ],
                ],
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: _tabController.index == 0
          ? FloatingActionButton.extended(
              backgroundColor: AppTheme.primaryGreen,
              icon: const Icon(Icons.add_task),
              label: const Text('Thêm việc'),
              onPressed: _showCreateTaskDialog,
            )
          : null,
    );
  }
}
