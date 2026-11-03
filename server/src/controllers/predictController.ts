import { Request, Response } from 'express';
import { predictWithLocalModel } from '../services/aiInferenceService.js';
import { analyzeImagePixelByPixel } from '../services/pixelAnalysisService.js';

export const PREDICT_MODEL_NAME = 'gari-convnext-models';
export const PREDICT_MODEL_TYPE = 'convnext_small (PyTorch/timm safetensors)';

export const predictController = async (req: Request, res: Response) => {
    const startTime = Date.now();
    try {
        const image = req.file?.buffer;
        if (!image) {
            return res.status(400).json({
                success: false,
                error: 'No image provided',
                message: 'Please upload an image file using the "image" field'
            });
        }

        const cropId = (req.body?.crop || req.query?.crop || 'auto').toString();

        try {
            // Run real machine learning model inference using PyTorch ConvNeXt-Small
            const aiResult = await predictWithLocalModel(image, cropId);
            return res.status(200).json(aiResult);
        } catch (aiErr: any) {
            console.error('❌ Local AI inference engine error:', aiErr);
            const status = aiErr?.statusCode || 400;
            return res.status(status).json({
                success: false,
                status: 'ERROR',
                crop: cropId,
                error: 'InferenceError',
                message: aiErr instanceof Error ? aiErr.message : String(aiErr),
                processing_time_ms: Date.now() - startTime,
                timestamp: new Date().toISOString()
            });
        }
    } catch (err) {
        return res.status(500).json({
            success: false,
            status: 'ERROR',
            message: err instanceof Error ? err.message : 'Unknown error',
            processing_time_ms: Date.now() - startTime,
            timestamp: new Date().toISOString()
        });
    }
};