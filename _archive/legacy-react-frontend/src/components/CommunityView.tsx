import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  BookOpen,
  Plus,
  Search,
  ThumbsUp,
  MessageCircle,
  CheckCircle,
  Award,
  X
} from 'lucide-react';

interface Post {
  id: number;
  title: string;
  content: string;
  crop_id?: string;
  region?: string;
  post_type: string;
  author_name?: string;
  author_is_expert?: boolean;
  author_expert_title?: string;
  author_institution?: string;
  is_official_guidance?: boolean;
  likes_count: number;
  comments_count: number;
  is_liked_by_me?: boolean;
  created_at?: string;
}

interface Article {
  id: number;
  title: string;
  summary: string;
  content: string;
  crop_id?: string;
  topic?: string;
  region?: string;
  author_name?: string;
  source_name?: string;
  review_status?: string;
  likes_count: number;
  is_liked_by_me?: boolean;
}

export const CommunityView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'feed' | 'library'>('feed');
  const [posts, setPosts] = useState<Post[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCrop, setSelectedCrop] = useState<string>('');
  const [selectedRegion, setSelectedRegion] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('');

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [createTitle, setCreateTitle] = useState<string>('');
  const [createContent, setCreateContent] = useState<string>('');
  const [createCrop, setCreateCrop] = useState<string>('');
  const [createRegion, setCreateRegion] = useState<string>('');
  const [submittingPost, setSubmittingPost] = useState<boolean>(false);

  // Read Article Modal
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);

  // Load Posts
  const fetchPosts = async () => {
    setLoading(true);
    try {
      let url = '/api/community/posts?limit=30';
      if (selectedCrop) url += `&crop_id=${encodeURIComponent(selectedCrop)}`;
      if (selectedRegion) url += `&region=${encodeURIComponent(selectedRegion)}`;
      if (selectedType) url += `&post_type=${encodeURIComponent(selectedType)}`;
      if (searchQuery) url += `&query=${encodeURIComponent(searchQuery)}`;

      const token = localStorage.getItem('gari_token') || sessionStorage.getItem('gari_token');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(url, { headers });
      const data = await res.json();
      if (data.success && data.posts) {
        setPosts(data.posts);
      }
    } catch (err) {
      console.warn('Failed to load community posts:', err);
    } finally {
      setLoading(false);
    }
  };

  // Load Articles
  const fetchArticles = async () => {
    setLoading(true);
    try {
      let url = '/api/knowledge/articles?limit=30';
      if (selectedCrop) url += `&crop_id=${encodeURIComponent(selectedCrop)}`;
      if (selectedRegion) url += `&region=${encodeURIComponent(selectedRegion)}`;
      if (searchQuery) url += `&query=${encodeURIComponent(searchQuery)}`;

      const token = localStorage.getItem('gari_token') || sessionStorage.getItem('gari_token');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(url, { headers });
      const data = await res.json();
      if (data.success && data.articles) {
        setArticles(data.articles);
      }
    } catch (err) {
      console.warn('Failed to load knowledge articles:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'feed') {
      fetchPosts();
    } else {
      fetchArticles();
    }
  }, [activeTab, selectedCrop, selectedRegion, selectedType]);

  const handleLikePost = async (id: number) => {
    const token = localStorage.getItem('gari_token') || sessionStorage.getItem('gari_token');
    if (!token) {
      alert('Vui lòng đăng nhập để thích bài viết!');
      return;
    }
    try {
      const res = await fetch(`/api/community/posts/${id}/like`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        setPosts(prev =>
          prev.map(p =>
            p.id === id
              ? {
                  ...p,
                  is_liked_by_me: data.liked,
                  likes_count: data.likes_count ?? (data.liked ? p.likes_count + 1 : p.likes_count - 1)
                }
              : p
          )
        );
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreatePostSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem('gari_token') || sessionStorage.getItem('gari_token');
    if (!token) {
      alert('Vui lòng đăng nhập trước khi tạo thảo luận!');
      return;
    }
    setSubmittingPost(true);
    try {
      const res = await fetch('/api/community/posts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          title: createTitle,
          content: createContent,
          crop_id: createCrop || undefined,
          region: createRegion || undefined,
          post_type: 'question'
        })
      });
      const data = await res.json();
      if (data.success) {
        setIsCreateModalOpen(false);
        setCreateTitle('');
        setCreateContent('');
        fetchPosts();
      } else {
        alert(data.detail || 'Không thể tạo bài viết.');
      }
    } catch (err: any) {
      alert('Lỗi: ' + err.message);
    } finally {
      setSubmittingPost(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-16">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#E5EBE6] dark:border-[#202C23] pb-5">
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold font-serif text-[#082D20] dark:text-[#ECFDF5] tracking-tight">
            Cộng đồng & Thư viện Tri thức Nông học
          </h1>
          <p className="text-sm text-[#526356] dark:text-[#97A69A] mt-1">
            Diễn đàn trao đổi thực địa, giải đáp kỹ thuật cùng chuyên gia và cẩm nang BVTV chính thống.
          </p>
        </div>

        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#087A43] hover:bg-[#066637] text-white font-medium text-sm transition-all shadow-sm active:scale-95"
        >
          <Plus className="w-4 h-4" />
          <span>Tạo bài thảo luận / Đặt câu hỏi</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#E5EBE6] dark:border-[#202C23] gap-6">
        <button
          onClick={() => setActiveTab('feed')}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'feed'
              ? 'border-[#087A43] text-[#087A43] dark:text-[#22C55E]'
              : 'border-transparent text-[#6B7A70] hover:text-[#17231C] dark:hover:text-[#F1F5F2]'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          <span>Hỏi đáp & Thảo luận Thực địa</span>
        </button>

        <button
          onClick={() => setActiveTab('library')}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'library'
              ? 'border-[#087A43] text-[#087A43] dark:text-[#22C55E]'
              : 'border-transparent text-[#6B7A70] hover:text-[#17231C] dark:hover:text-[#F1F5F2]'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          <span>Cẩm nang Tri thức & Khuyến nông</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-[#151C17] border border-[#E5EBE6] dark:border-[#232F26] rounded-2xl p-4 flex flex-wrap gap-3 items-center shadow-xs">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#8F9E93]" />
          <input
            type="text"
            placeholder={activeTab === 'feed' ? 'Tìm bài viết, dịch hại, triệu chứng...' : 'Tìm cẩm nang, tài liệu BVTV...'}
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && (activeTab === 'feed' ? fetchPosts() : fetchArticles())}
            className="w-full pl-9 pr-3 py-2 text-sm bg-[#F5F8F5] dark:bg-[#1C261F] border border-[#E5EBE5] dark:border-[#232F26] rounded-xl text-[#17231C] dark:text-[#EDF2EE] focus:outline-none focus:border-[#087A43]"
          />
        </div>

        <select
          value={selectedCrop}
          onChange={e => setSelectedCrop(e.target.value)}
          className="px-3 py-2 text-sm bg-[#F5F8F5] dark:bg-[#1C261F] border border-[#E5EBE5] dark:border-[#232F26] rounded-xl text-[#17231C] dark:text-[#EDF2EE]"
        >
          <option value="">Tất cả cây trồng</option>
          <option value="rice">Lúa</option>
          <option value="coffee">Cà phê</option>
          <option value="pepper">Hồ tiêu</option>
          <option value="durian">Sầu riêng</option>
          <option value="tomato">Cà chua</option>
        </select>

        <select
          value={selectedRegion}
          onChange={e => setSelectedRegion(e.target.value)}
          className="px-3 py-2 text-sm bg-[#F5F8F5] dark:bg-[#1C261F] border border-[#E5EBE5] dark:border-[#232F26] rounded-xl text-[#17231C] dark:text-[#EDF2EE]"
        >
          <option value="">Tất cả vùng</option>
          <option value="mien_bac">Miền Bắc (ĐBSH & Tây Bắc)</option>
          <option value="tay_nguyen">Tây Nguyên</option>
          <option value="mien_nam">Miền Nam (ĐBSCL)</option>
        </select>

        {activeTab === 'feed' && (
          <select
            value={selectedType}
            onChange={e => setSelectedType(e.target.value)}
            className="px-3 py-2 text-sm bg-[#F5F8F5] dark:bg-[#1C261F] border border-[#E5EBE5] dark:border-[#232F26] rounded-xl text-[#17231C] dark:text-[#EDF2EE]"
          >
            <option value="">Tất cả chủ đề</option>
            <option value="question">Câu hỏi thực địa</option>
            <option value="experience">Kinh nghiệm canh tác</option>
            <option value="pest_alert">Cảnh báo sâu bệnh</option>
          </select>
        )}
      </div>

      {/* Feed Stream */}
      {activeTab === 'feed' ? (
        <div className="space-y-4">
          {loading ? (
            <div className="text-center py-12 text-[#6B7A70]">Đang tải dữ liệu thảo luận...</div>
          ) : posts.length === 0 ? (
            <div className="text-center py-16 bg-white dark:bg-[#151C17] rounded-2xl border border-dashed border-[#E5EBE6] dark:border-[#232F26] p-8">
              <MessageSquare className="w-10 h-10 mx-auto text-[#8F9E93] mb-3" />
              <p className="font-semibold text-[#17231C] dark:text-[#EDF2EE]">Chưa có bài thảo luận nào phù hợp</p>
              <p className="text-xs text-[#6B7A70] mt-1">Hãy là người đầu tiên đặt câu hỏi thực địa!</p>
            </div>
          ) : (
            posts.map(p => (
              <div
                key={p.id}
                className="bg-white dark:bg-[#151C17] border border-[#E5EBE6] dark:border-[#232F26] rounded-2xl p-5 shadow-xs hover:border-[#087A43]/40 transition-all space-y-3"
              >
                {/* Author row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-[#E8F6EC] dark:bg-[#1C261F] text-[#087A43] dark:text-[#22C55E] flex items-center justify-center font-bold text-sm">
                      {(p.author_name || 'U').charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm text-[#17231C] dark:text-[#EDF2EE]">
                          {p.author_name || 'Nông dân GARI'}
                        </span>
                        {p.author_is_expert && (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                            <CheckCircle className="w-3 h-3" />
                            Chuyên gia {p.author_expert_title || 'Nông học'}
                          </span>
                        )}
                        {p.is_official_guidance && (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                            <Award className="w-3 h-3" />
                            Khuyến cáo chính thống
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-[#6B7A70] flex items-center gap-2 mt-0.5">
                        <span>{p.region || 'Toàn quốc'}</span>
                        <span>•</span>
                        <span>Cây: {p.crop_id ? p.crop_id.toUpperCase() : 'Chung'}</span>
                        <span>•</span>
                        <span>{p.created_at ? p.created_at.substring(0, 10) : ''}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Content */}
                <h3 className="font-bold text-base text-[#17231C] dark:text-[#EDF2EE]">{p.title}</h3>
                <p className="text-sm text-[#38483D] dark:text-[#C5D2C8] leading-relaxed whitespace-pre-line">{p.content}</p>

                {/* Actions */}
                <div className="flex items-center gap-4 pt-2 border-t border-[#F0F4F1] dark:border-[#1C261F] text-xs font-medium text-[#6B7A70]">
                  <button
                    onClick={() => handleLikePost(p.id)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                      p.is_liked_by_me
                        ? 'bg-[#E8F6EC] text-[#087A43] dark:bg-[#1C261F] dark:text-[#22C55E]'
                        : 'hover:bg-[#F5F8F5] dark:hover:bg-[#1C261F]'
                    }`}
                  >
                    <ThumbsUp className="w-3.5 h-3.5" />
                    <span>{p.likes_count || 0} Thích</span>
                  </button>

                  <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg">
                    <MessageCircle className="w-3.5 h-3.5" />
                    <span>{p.comments_count || 0} Bình luận</span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* Library Stream */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {loading ? (
            <div className="col-span-2 text-center py-12 text-[#6B7A70]">Đang tải thư viện tri thức...</div>
          ) : articles.length === 0 ? (
            <div className="col-span-2 text-center py-16 bg-white dark:bg-[#151C17] rounded-2xl border border-dashed border-[#E5EBE6] dark:border-[#232F26] p-8">
              <BookOpen className="w-10 h-10 mx-auto text-[#8F9E93] mb-3" />
              <p className="font-semibold text-[#17231C] dark:text-[#EDF2EE]">Chưa có bài cẩm nang phù hợp</p>
            </div>
          ) : (
            articles.map(art => (
              <div
                key={art.id}
                onClick={() => setSelectedArticle(art)}
                className="bg-white dark:bg-[#151C17] border border-[#E5EBE6] dark:border-[#232F26] rounded-2xl p-5 shadow-xs hover:border-[#087A43] cursor-pointer transition-all flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-[#087A43] dark:text-[#22C55E] font-semibold">
                    <span>{art.topic || 'BVTV Thực địa'}</span>
                    <span className="text-[#6B7A70]">{art.region || 'Toàn quốc'}</span>
                  </div>
                  <h3 className="font-bold text-base text-[#17231C] dark:text-[#EDF2EE] leading-snug">{art.title}</h3>
                  <p className="text-xs text-[#526356] dark:text-[#97A69A] line-clamp-3 leading-relaxed">{art.summary}</p>
                </div>

                <div className="flex items-center justify-between pt-4 mt-4 border-t border-[#F0F4F1] dark:border-[#1C261F] text-xs text-[#6B7A70]">
                  <span>Nguồn: {art.source_name || 'Viện BVTV'}</span>
                  <span className="text-[#087A43] font-medium hover:underline">Đọc toàn văn →</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Create Post Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-[#151C17] border border-[#E5EBE6] dark:border-[#232F26] rounded-2xl max-w-xl w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E5EBE6] dark:border-[#202C23] pb-3">
              <h3 className="font-bold text-lg text-[#17231C] dark:text-[#EDF2EE]">Đặt câu hỏi / Tạo thảo luận thực địa</h3>
              <button onClick={() => setIsCreateModalOpen(false)} className="text-[#6B7A70] hover:text-[#17231C]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreatePostSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#17231C] dark:text-[#EDF2EE] mb-1">Tiêu đề bài viết *</label>
                <input
                  type="text"
                  required
                  placeholder="Ví dụ: Vườn cà chua có triệu chứng cháy lá sau mưa, xin tư vấn..."
                  value={createTitle}
                  onChange={e => setCreateTitle(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-[#F5F8F5] dark:bg-[#1C261F] border border-[#E5EBE5] dark:border-[#232F26] rounded-xl text-[#17231C] dark:text-[#EDF2EE] focus:outline-none focus:border-[#087A43]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#17231C] dark:text-[#EDF2EE] mb-1">Cây trồng liên quan</label>
                  <select
                    value={createCrop}
                    onChange={e => setCreateCrop(e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-[#F5F8F5] dark:bg-[#1C261F] border border-[#E5EBE5] dark:border-[#232F26] rounded-xl text-[#17231C] dark:text-[#EDF2EE]"
                  >
                    <option value="">Chọn loại cây</option>
                    <option value="rice">Lúa</option>
                    <option value="coffee">Cà phê</option>
                    <option value="pepper">Hồ tiêu</option>
                    <option value="durian">Sầu riêng</option>
                    <option value="tomato">Cà chua</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#17231C] dark:text-[#EDF2EE] mb-1">Khu vực thực địa</label>
                  <select
                    value={createRegion}
                    onChange={e => setCreateRegion(e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-[#F5F8F5] dark:bg-[#1C261F] border border-[#E5EBE5] dark:border-[#232F26] rounded-xl text-[#17231C] dark:text-[#EDF2EE]"
                  >
                    <option value="">Chọn vùng</option>
                    <option value="Ba Vì, Hà Nội">Ba Vì, Hà Nội</option>
                    <option value="Đồng bằng Sông Hồng">Đồng bằng Sông Hồng</option>
                    <option value="Tây Nguyên">Tây Nguyên</option>
                    <option value="Đồng bằng Sông Cửu Long">Đồng bằng Sông Cửu Long</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#17231C] dark:text-[#EDF2EE] mb-1">Nội dung chi tiết *</label>
                <textarea
                  required
                  rows={5}
                  placeholder="Mô tả kỹ triệu chứng, diện tích, thời điểm xuất hiện và các loại thuốc/phân bón đã sử dụng gần đây..."
                  value={createContent}
                  onChange={e => setCreateContent(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-[#F5F8F5] dark:bg-[#1C261F] border border-[#E5EBE5] dark:border-[#232F26] rounded-xl text-[#17231C] dark:text-[#EDF2EE] focus:outline-none focus:border-[#087A43]"
                ></textarea>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 text-sm rounded-xl border border-[#E5EBE5] dark:border-[#232F26] text-[#6B7A70]"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={submittingPost}
                  className="px-5 py-2 text-sm rounded-xl bg-[#087A43] hover:bg-[#066637] text-white font-medium disabled:opacity-50"
                >
                  {submittingPost ? 'Đang đăng...' : 'Đăng thảo luận'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Read Article Modal */}
      {selectedArticle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-[#151C17] border border-[#E5EBE6] dark:border-[#232F26] rounded-2xl max-w-2xl w-full p-6 shadow-xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#E5EBE6] dark:border-[#202C23] pb-3">
              <div>
                <span className="text-xs font-bold text-[#087A43]">{selectedArticle.topic}</span>
                <h3 className="font-bold text-lg text-[#17231C] dark:text-[#EDF2EE]">{selectedArticle.title}</h3>
              </div>
              <button onClick={() => setSelectedArticle(null)} className="text-[#6B7A70] hover:text-[#17231C]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-[#E8F6EC] dark:bg-[#1C261F] p-3 rounded-xl text-xs text-[#087A43] dark:text-[#22C55E] italic">
              {selectedArticle.summary}
            </div>

            <div className="text-sm text-[#38483D] dark:text-[#C5D2C8] leading-relaxed whitespace-pre-line">
              {selectedArticle.content}
            </div>

            <div className="pt-4 border-t border-[#E5EBE6] dark:border-[#202C23] flex justify-between items-center text-xs text-[#6B7A70]">
              <span>Tác giả: {selectedArticle.author_name || selectedArticle.source_name}</span>
              <button onClick={() => setSelectedArticle(null)} className="px-4 py-2 bg-[#087A43] text-white rounded-xl">
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
