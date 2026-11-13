import OpenAI from 'openai';
import databaseService from './databaseService';

// OpenAI configuration
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || '';

const openai = new OpenAI({
    apiKey: OPENAI_API_KEY,
});

/**
 * Chatbot AI sử dụng OpenAI để tư vấn về bệnh cây trồng
 */
export async function getChatbotResponse(message: string): Promise<string> {
    try {
        const completion = await openai.chat.completions.create({
            model: "gpt-3.5-turbo",
            messages: [
                {
                    role: "system",
                    content: `Bạn là một chuyên gia AI về bệnh cây trồng và nông nghiệp tại Việt Nam. 
          Hãy trả lời bằng tiếng Việt một cách thân thiện và chuyên nghiệp.
          Tập trung vào:
          - Chẩn đoán bệnh cây trồng
          - Phương pháp phòng chống và điều trị
          - Chăm sóc cây trồng tại Việt Nam
          - Sử dụng thuốc bảo vệ thực vật an toàn
          
          Luôn đề xuất người dùng tải lên ảnh để có chẩn đoán chính xác hơn.
          Giữ câu trả lời ngắn gọn, dễ hiểu (khoảng 2-3 câu).`
                },
                {
                    role: "user",
                    content: message
                }
            ],
            max_tokens: 200,
            temperature: 0.7,
        });

        return completion.choices[0]?.message?.content || 'Xin lỗi, tôi không thể trả lời câu hỏi này lúc này.';

    } catch (error: any) {
        console.error('❌ Lỗi OpenAI API:', error.message);

        // Xử lý các lỗi cụ thể
        if (error.status === 429) {
            console.error('⚠️ Hạn mức OpenAI đã vượt quá. Chuyển sang mode offline.');
            return "⚠️ Hiện tại tôi đang hoạt động ở chế độ giới hạn do hạn mức API. Tôi vẫn có thể tư vấn cơ bản: " + getSimpleBotResponse(message);
        } else if (error.status === 401) {
            console.error('⚠️ API key OpenAI không hợp lệ.');
            return "🔧 Hệ thống đang bảo trì. Tôi vẫn có thể tư vấn cơ bản: " + getSimpleBotResponse(message);
        }

        // Fallback to simple responses if OpenAI fails
        return "🤖 Tôi đang gặp vấn đề kỹ thuật nhỏ, nhưng vẫn có thể giúp bạn: " + getSimpleBotResponse(message);
    }
}

/**
 * Phản hồi đơn giản khi OpenAI không khả dụng
 */
function getSimpleBotResponse(message: string): string {
    const lowerMsg = message.toLowerCase();

    if (lowerMsg.includes('bệnh') || lowerMsg.includes('ốm') || lowerMsg.includes('chết')) {
        return "🏥 Tôi có thể giúp chẩn đoán bệnh cây! Tải lên ảnh để AI phân tích, hoặc mô tả triệu chứng bạn thấy trên cây. Bạn cũng có thể tìm kiếm trong cơ sở dữ liệu bệnh ở phía trên.";
    }

    if (lowerMsg.includes('nước') || lowerMsg.includes('tưới')) {
        return "💧 **Tưới nước đúng cách:**\n- Tưới khi lớp đất trên cùng khô 2-3cm\n- Tưới sâu nhưng không thường xuyên\n- Tưới buổi sáng là tốt nhất\n- Tránh tưới lên lá để ngăn bệnh nấm";
    }

    if (lowerMsg.includes('phân') || lowerMsg.includes('bón') || lowerMsg.includes('dinh dưỡng')) {
        return "🌱 **Bón phân hiệu quả:**\n- Dùng phân cân bằng NPK trong mùa sinh trưởng\n- Bón quá nhiều đạm làm cây dễ bị bệnh\n- Phân hữu cơ tốt hơn phân hóa học\n- Bón vào buổi chiều mát";
    }

    if (lowerMsg.includes('đốm') || lowerMsg.includes('nâu') || lowerMsg.includes('vàng') || lowerMsg.includes('lá')) {
        return "🍃 **Lá đổi màu - nguyên nhân:**\n- 🔵 Vàng lá: thiếu đạm, tưới quá nhiều, già tự nhiên\n- 🟤 Nâu lá: thiếu nước, bệnh nấm, cháy nắng\n- ⚫ Đốm đen: bệnh nấm, vi khuẩn\n\n💡 Tải ảnh lên để chẩn đoán chính xác!";
    }

    if (lowerMsg.includes('phòng') || lowerMsg.includes('ngăn chặn') || lowerMsg.includes('tránh')) {
        return "🛡️ **5 nguyên tắc phòng bệnh:**\n1. 🌬️ Đảm bảo thông gió tốt\n2. 💧 Tưới ở gốc, không tưới lên lá\n3. 🗑️ Loại bỏ lá, cành bệnh ngay lập tức\n4. 📏 Giãn cách hợp lý giữa các cây\n5. 🧬 Chọn giống kháng bệnh";
    }

    if (lowerMsg.includes('nấm') || lowerMsg.includes('fungus')) {
        return "🍄 **Bệnh nấm - cách xử lý:**\n- Cải thiện thông gió, giảm độ ẩm\n- Cắt bỏ phần bị nhiễm\n- Xịt thuốc diệt nấm sinh học\n- Tránh tưới lên lá\n- Vệ sinh dụng cụ sau mỗi lần cắt";
    }

    if (lowerMsg.includes('sâu') || lowerMsg.includes('côn trùng') || lowerMsg.includes('pest')) {
        return "🐛 **Kiểm soát sâu bệnh:**\n- Quan sát cây hàng ngày\n- Dùng bẫy dính màu vàng\n- Xịt nước xà phòng pha loãng\n- Trồng cây đuổi sâu (cúc tần ô, húng quế)\n- Thuốc BVTV chỉ dùng khi cần thiết";
    }

    if (lowerMsg.includes('xin chào') || lowerMsg.includes('chào') || lowerMsg.includes('hello') || lowerMsg.includes('hi')) {
        return "Xin chào! 🌿 Tôi là AI Bác Sĩ Cây Trồng. Tôi có thể giúp:\n\n🔍 Chẩn đoán bệnh qua ảnh\n📚 Tra cứu thông tin bệnh cây\n💡 Tư vấn chăm sóc và phòng bệnh\n🌱 Hướng dẫn trồng cây khỏe mạnh\n\nHôm nay tôi có thể giúp gì cho cây của bạn?";
    }

    if (lowerMsg.includes('cảm ơn') || lowerMsg.includes('thank')) {
        return "Rất vui được giúp đỡ! 🌱 Chúc cây của bạn luôn xanh tốt và khỏe mạnh. Hãy nhớ quan sát cây thường xuyên và chăm sóc đúng cách nhé! 🌿✨";
    }

    // Default response với gợi ý cụ thể
    const suggestions = [
        "💡 **Tôi có thể tư vấn về:**\n- Chẩn đoán bệnh cây (tải ảnh lên)\n- Cách tưới nước, bón phân\n- Phòng chống sâu bệnh\n- Chăm sóc cây theo mùa\n\n❓ Bạn muốn hỏi về vấn đề gì cụ thể?",
        "🌿 **Mẹo chăm cây:**\nHãy mô tả triệu chứng cây của bạn, tôi sẽ tư vấn cách xử lý. Hoặc tải ảnh lên để được chẩn đoán chính xác hơn!",
        "📋 **Tôi có thể giúp:**\n- Tìm hiểu nguyên nhân lá vàng, đốm lá\n- Hướng dẫn xử lý bệnh nấm, sâu bệnh\n- Tư vấn thời điểm tưới, bón phân\n\nBạn cần hỗ trợ gì?"
    ];

    return suggestions[Math.floor(Math.random() * suggestions.length)];
}

export default { getChatbotResponse };