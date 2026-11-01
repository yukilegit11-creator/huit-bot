-- ==============================================================================
-- BẢNG LƯU TRỮ BÀI VIẾT CÀO TỪ FACEBOOK TRÊN SUPABASE (HUIT SOCIAL FEED)
-- Chạy đoạn script này trong: Supabase Dashboard -> SQL Editor -> Run
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,
    description TEXT,
    category TEXT DEFAULT 'Facebook',
    status TEXT DEFAULT 'published',
    page_name TEXT,
    author TEXT,
    post_url TEXT,
    posted_time TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Phân quyền cho phép Web và Bot đọc/ghi dữ liệu công khai qua Supabase API
ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Cho phép đọc bài viết công khai" 
ON public.posts FOR SELECT USING (true);

CREATE POLICY "Cho phép bot thêm bài viết mới" 
ON public.posts FOR INSERT WITH CHECK (true);

CREATE POLICY "Cho phép bot cập nhật bài viết" 
ON public.posts FOR UPDATE USING (true);
