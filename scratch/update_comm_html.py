import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/community.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the broken script tag loading with ES Module setup
old_script_start = '''    <script src="/static/frontend2/app.js?v=20261104_stable"></script>
    <script>
        let currentTab = 'feed';'''

new_script_start = '''    <script type="module">
        import { setupSaaSShell, fetchJSON, toast } from '/static/frontend2/app.js?v=20261104_stable';

        // Initialize GARI SaaS Shell for Community & Agricultural Knowledge
        setupSaaSShell('community', 'Cộng đồng & Tri thức Nông học', false);

        let currentTab = 'feed';'''

if old_script_start not in text:
    print("Error: old_script_start not found in community.html")
    sys.exit(1)

text = text.replace(old_script_start, new_script_start, 1)

# Before the closing </script>, bind all functions to window
old_script_end = '''        document.addEventListener('DOMContentLoaded', () => {
            loadCommunityPosts();
        });
    </script>'''

new_script_end = '''        // Expose functions to window for inline HTML onclick/onchange/onkeydown handlers
        window.switchTab = switchTab;
        window.loadCommunityPosts = loadCommunityPosts;
        window.renderPosts = renderPosts;
        window.toggleLikePost = toggleLikePost;
        window.toggleComments = toggleComments;
        window.loadComments = loadComments;
        window.submitComment = submitComment;
        window.loadKnowledgeArticles = loadKnowledgeArticles;
        window.renderArticles = renderArticles;
        window.readArticle = readArticle;
        window.closeArticleModal = closeArticleModal;
        window.openCreatePostModal = openCreatePostModal;
        window.closeCreatePostModal = closeCreatePostModal;
        window.handleCreatePost = handleCreatePost;
        window.openReportModal = openReportModal;
        window.closeReportModal = closeReportModal;
        window.handleSendReport = handleSendReport;
        window.handlePostSearch = handlePostSearch;
        window.handleLibSearch = handleLibSearch;

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                loadCommunityPosts();
            });
        } else {
            loadCommunityPosts();
        }
    </script>'''

if old_script_end not in text:
    print("Error: old_script_end not found in community.html")
    sys.exit(1)

text = text.replace(old_script_end, new_script_end, 1)

with open('frontend2/community.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully updated frontend2/community.html!")
