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
    uint8_t src;   //id
    uint8_t type;  //消息类型
    uint16_t seq;  //sequence
    uint32_t lat;   //纬度*1e7  
    uint32_t lon;   //精度*1e7
}

}
