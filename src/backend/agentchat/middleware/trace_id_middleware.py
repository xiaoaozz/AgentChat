from time import time
import traceback
from uuid import uuid4
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from loguru import logger

from agentchat.utils.contexts import set_trace_id_context


class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    请求跟踪中间件，用于为每个请求生成唯一的追踪ID
    实现分布式追踪功能，便于日志关联和问题排查
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # 生成trace id: 优先使用请求头中的 x-b3-traceid（支持分布式追踪），否则生成新的UUID
        trace_id = request.headers.get("x-b3-traceid", str(uuid4()))
        
        # 记录请求开始时间，用于计算耗时
        start_time = time()
        
        # 设定trace id到上下文中，使得在整个请求生命周期内都可以访问
        set_trace_id_context(trace_id)

        # 将trace_id添加到日志上下文，后续日志都会自动包含该trace_id
        with logger.contextualize(trace_id=trace_id):
            try:
                # 调用下一个中间件或路由处理器
                response = await call_next(request)
            except Exception:
                # 捕获所有未处理的异常，记录详细堆栈信息
                logger.error(f"exception_traceback: {traceback.format_exc()}")
                # 返回统一的错误响应
                response = JSONResponse(
                    status_code=500,
                    content={"code": -1, "error_msg": "10500: 系统错误，请重试"}
                )

            # 将trace_id添加到响应头，方便客户端进行问题追踪
            response.headers["X-Trace-ID"] = trace_id
            
            # 记录请求日志：方法、路径、状态码和耗时（毫秒）
            logger.info(
                f'{request.method} {request.url.path} {response.status_code} time_cost={(time() - start_time) * 1000:.3f}ms')
            return response
