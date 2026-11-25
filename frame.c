#ifndef FRAME_H
#define FRAME_H

#include <stdint.h>
#include <stddef.h>

#ifdef  __cplusplus
extern "C"{
#endif

#define FRAME_LEN   16 //3.3帧固定字长16字节
#define FRAME_TTL_INIT   3//3.1TTL初值


#define MSG_HEARTBEAT 0x01u
#define MSG_POSITION  0x02u
#define MSG_TARGET    0x03u
#define MSG_CLAIM     0x04u
#define MSG_STATUS    0x05u
#define MSG_TEXT      0x06u
#define MSG_CONTROL   0x07u
#define MSG_REQUEST   0x08u
#define MSG_GRANT     0x09u

typedef struct {
    uint8_t  src;      /* 源 ID */
    uint8_t  type;     /* 消息类型 */
    uint16_t seq;      /* 序号，小端，可回绕 */
    int32_t  lat;      /* 纬度 × 1e7 */
    int32_t  lon;      /* 经度 × 1e7 */
    int16_t  alt;      /* 高度，单位分米；用有符号以支持相对高度 */
    uint8_t  status;   /* 高 4 bit 电量档 0–15，低 4 bit 阶段 */
    uint8_t  ttl;      /* 剩余跳数 */
} frame_t;

}
