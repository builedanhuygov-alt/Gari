import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/app_theme.dart';
import '../core/constants.dart';
import '../models/community_post_model.dart';
import '../models/knowledge_article_model.dart';

class CommunityScreen extends StatefulWidget {
  const CommunityScreen({super.key});

  @override
  State<CommunityScreen> createState() => _CommunityScreenState();
}

class _CommunityScreenState extends State<CommunityScreen> with SingleTickerProviderStateMixin {
  final ApiClient _api = ApiClient();
  late TabController _tabController;

  // Knowledge Library State
  List<KnowledgeArticleModel> _articles = [];
  bool _isLoadingArticles = false;
  String _selectedCrop = 'all';
  final TextEditingController _searchCtrl = TextEditingController();

  // Community Feed State
  List<CommunityPostModel> _posts = [];
  bool _isLoadingPosts = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadArticles();
    _loadPosts();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadArticles() async {
    setState(() => _isLoadingArticles = true);
    final articles = await _api.getKnowledgeArticles(
      cropId: _selectedCrop == 'all' ? null : _selectedCrop,
      search: _searchCtrl.text.trim().isEmpty ? null : _searchCtrl.text.trim(),
    );
    if (mounted) {
      setState(() {
        _articles = articles;
        _isLoadingArticles = false;
      });
    }
  }

  Future<void> _loadPosts() async {
    setState(() => _isLoadingPosts = true);
    final posts = await _api.getCommunityPosts(
      cropId: _selectedCrop == 'all' ? null : _selectedCrop,
    );
    if (mounted) {
      setState(() {
        _posts = posts;
        _isLoadingPosts = false;
      });
    }
  }

  void _showCreatePostDialog() {
    final titleCtrl = TextEditingController();
    final contentCtrl = TextEditingController();
    String cropId = 'tomato';
    final regionCtrl = TextEditingController(text: 'Tây Nguyên');

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
                  const Text('Đặt câu hỏi cộng đồng', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(ctx)),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: titleCtrl,
                decoration: const InputDecoration(labelText: 'Tiêu đề câu hỏi / Vấn đề', isDense: true),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: contentCtrl,
                maxLines: 3,
                decoration: const InputDecoration(labelText: 'Chi tiết hiện trạng bệnh & vườn', isDense: true),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  const Text('Cây trồng: '),
                  const SizedBox(width: 8),
                  DropdownButton<String>(
                    value: cropId,
                    items: AppConstants.primaryCrops.where((c) => c.id != 'all').map((c) {
                      return DropdownMenuItem(value: c.id, child: Text('${c.icon} ${c.nameVi}'));
                    }).toList(),
                    onChanged: (val) {
                      if (val != null) setSheetState(() => cropId = val);
                    },
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                icon: const Icon(Icons.send),
                label: const Text('Đăng câu hỏi'),
                onPressed: () async {
                  if (titleCtrl.text.trim().isEmpty || contentCtrl.text.trim().isEmpty) return;
                  Navigator.pop(ctx);
                  final post = await _api.createCommunityPost(
                    title: titleCtrl.text.trim(),
                    content: contentCtrl.text.trim(),
                    cropId: cropId,
                    region: regionCtrl.text.trim(),
                  );
                  if (post != null) {
                    _loadPosts();
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Đã gửi câu hỏi lên cộng đồng nông nghiệp!')),
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

  void _viewArticleDetail(KnowledgeArticleModel article) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(article.title),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 6,
                children: [
                  Chip(label: Text(article.cropId.toUpperCase()), backgroundColor: AppTheme.primaryLight.withAlpha(50)),
                  if (article.isOfficialGuidance)
                    const Chip(
                      avatar: Icon(Icons.verified, size: 16, color: AppTheme.primaryGreen),
                      label: Text('Tài liệu VietGAP chính thức'),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              if (article.summary.isNotEmpty)
                Text(
                  article.summary,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontStyle: FontStyle.italic),
                ),
              const Divider(height: 24),
              Text(article.content, style: const TextStyle(height: 1.5)),
              const SizedBox(height: 16),
              if (article.sourceCitation != null)
                Text('Nguồn trích dẫn: ${article.sourceCitation}', style: const TextStyle(fontSize: 12, color: Colors.grey)),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Đóng')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Cộng Đồng & Tri Thức'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.menu_book), text: 'Thư Viện'),
            Tab(icon: Icon(Icons.forum), text: 'Diễn Đàn'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          // TAB 1: KNOWLEDGE LIBRARY
          RefreshIndicator(
            onRefresh: _loadArticles,
            color: AppTheme.primaryGreen,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Search Bar
                TextField(
                  controller: _searchCtrl,
                  decoration: InputDecoration(
                    hintText: 'Tìm tài liệu, sâu bệnh, kỹ thuật...',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: IconButton(
                      icon: const Icon(Icons.arrow_forward),
                      onPressed: _loadArticles,
                    ),
                    filled: true,
                    fillColor: Colors.white,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                  ),
                  onSubmitted: (_) => _loadArticles(),
                ),
                const SizedBox(height: 12),

                // Crop Filter Chips
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: AppConstants.primaryCrops.map((crop) {
                      final isSelected = _selectedCrop == crop.id;
                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          avatar: Text(crop.icon),
                          label: Text(crop.nameVi),
                          selected: isSelected,
                          onSelected: (val) {
                            setState(() => _selectedCrop = crop.id);
                            _loadArticles();
                            _loadPosts();
                          },
                        ),
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 16),

                if (_isLoadingArticles)
                  const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator(color: AppTheme.primaryGreen)))
                else if (_articles.isEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        children: const [
                          Icon(Icons.search_off, size: 48, color: Colors.grey),
                          SizedBox(height: 12),
                          Text('Không tìm thấy tài liệu phù hợp.', style: TextStyle(color: Colors.grey)),
                        ],
                      ),
                    ),
                  )
                else
                  ..._articles.map((art) => Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(12),
                          onTap: () => _viewArticleDetail(art),
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    if (art.isOfficialGuidance)
                                      const Icon(Icons.verified, size: 18, color: AppTheme.primaryGreen),
                                    if (art.isOfficialGuidance) const SizedBox(width: 4),
                                    Text(
                                      art.category.toUpperCase(),
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        color: art.isOfficialGuidance ? AppTheme.primaryGreen : Colors.grey,
                                      ),
                                    ),
                                    const Spacer(),
                                    Text(art.cropId.toUpperCase(), style: const TextStyle(fontSize: 11, color: Colors.grey)),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Text(art.title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                                if (art.summary.isNotEmpty) ...[
                                  const SizedBox(height: 6),
                                  Text(art.summary, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.black87, fontSize: 13)),
                                ],
                                const SizedBox(height: 12),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text('Tác giả: ${art.authorName}', style: const TextStyle(fontSize: 12, color: Colors.grey)),
                                    const Text('Xem chi tiết →', style: TextStyle(color: AppTheme.primaryGreen, fontWeight: FontWeight.w600, fontSize: 12)),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      )),
              ],
            ),
          ),

          // TAB 2: COMMUNITY FORUM
          RefreshIndicator(
            onRefresh: _loadPosts,
            color: AppTheme.primaryGreen,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_isLoadingPosts)
                  const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator(color: AppTheme.primaryGreen)))
                else if (_posts.isEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        children: const [
                          Icon(Icons.forum_outlined, size: 48, color: Colors.grey),
                          SizedBox(height: 12),
                          Text('Chưa có câu hỏi nào trong chuyên mục này.', style: TextStyle(color: Colors.grey)),
                        ],
                      ),
                    ),
                  )
                else
                  ..._posts.map((post) => Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  CircleAvatar(
                                    radius: 16,
                                    backgroundColor: post.isExpert ? AppTheme.primaryGreen.withAlpha(40) : Colors.grey.withAlpha(40),
                                    child: Icon(post.isExpert ? Icons.verified_user : Icons.person, size: 18, color: post.isExpert ? AppTheme.primaryGreen : Colors.grey),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Text(post.authorName, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13.5)),
                                            if (post.isExpert) ...[
                                              const SizedBox(width: 4),
                                              const Icon(Icons.verified, size: 14, color: AppTheme.primaryGreen),
                                            ],
                                          ],
                                        ),
                                        Text(post.cropId.toUpperCase(), style: const TextStyle(color: Colors.grey, fontSize: 11)),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Text(post.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                              const SizedBox(height: 6),
                              Text(post.content, style: const TextStyle(fontSize: 13.5, height: 1.4)),
                              const SizedBox(height: 12),
                              Row(
                                children: [
                                  InkWell(
                                    onTap: () async {
                                      final isNowLiked = await _api.togglePostLike(post.id);
                                      setState(() {
                                        final idx = _posts.indexWhere((p) => p.id == post.id);
                                        if (idx != -1) {
                                          _posts[idx] = post.copyWith(
                                            isLiked: isNowLiked,
                                            likesCount: post.likesCount + (isNowLiked ? 1 : -1),
                                          );
                                        }
                                      });
                                    },
                                    borderRadius: BorderRadius.circular(20),
                                    child: Padding(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                      child: Row(
                                        children: [
                                          Icon(
                                            post.isLiked ? Icons.favorite : Icons.favorite_border,
                                            size: 18,
                                            color: post.isLiked ? AppTheme.accentRed : Colors.grey,
                                          ),
                                          const SizedBox(width: 4),
                                          Text('${post.likesCount}', style: TextStyle(color: post.isLiked ? AppTheme.accentRed : Colors.grey, fontSize: 13)),
                                        ],
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 16),
                                  Row(
                                    children: [
                                      const Icon(Icons.chat_bubble_outline, size: 18, color: Colors.grey),
                                      const SizedBox(width: 4),
                                      Text('${post.commentsCount}', style: const TextStyle(color: Colors.grey, fontSize: 13)),
                                    ],
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      )),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppTheme.primaryGreen,
        icon: const Icon(Icons.add_comment),
        label: const Text('Đặt câu hỏi'),
        onPressed: _showCreatePostDialog,
      ),
    );
  }
}
