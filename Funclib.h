//
//  Funclib.h
//  Funclib
//
//  Created by 廖海洲 on 12-11-12.
//  Copyright (c) 2012年 Topsee. All rights reserved.
//

#ifndef Funclib_Funclib_h
#define Funclib_Funclib_h

#ifdef _WIN32
#if defined(FUNCLIB_EXPORT)
#  define FUNCLIB_LIBRARY __declspec(dllexport)
#else
#  define FUNCLIB_LIBRARY __declspec(dllimport)
#endif
#else
#  define FUNCLIB_LIBRARY
#endif


#ifdef _WIN32  //修改原有类型代码兼容window平台x64
    #ifdef _WIN64
        typedef long long LONG_EX;
        typedef unsigned long long ULONG_EX;
    #else
        typedef long LONG_EX;
        typedef unsigned long ULONG_EX;
    #endif
#else
    typedef long LONG_EX;
    typedef unsigned long ULONG_EX;
#endif


#ifdef __cplusplus
extern "C"
{
#endif

#define TPS_MSG_BASE (0x2000)
// IP字符串最大长度
#define MAX_IP_STRING_LEN 64

/************************************************************************************************************************
*                                        xml 摄像机设备数据格式定义说明                                                          *
*************************************************************************************************************************／
<?xml version="1.0" encoding="utf-8"?>
<DeviceList>
    <Device>
        <DevId>设备id</DevId>
        <DevName>设备名称</DevName>
        <DevGroupName>设备所属组名称</DevGroupName>
        <OnLine>设备是否在线,0:offline,1:heartbeat lost,2:active online</OnLine>
        <WithPTZ>是否支持云台控制,0:false,1:true</WithPTZ>
        <DoubleStream>是否支持双码流,0:false,1:true</DoubleStream>
        <RecStatus>是否处于录像状态,0:false,1:true</RecStatus>
        <VisitStreamOption>允许访问的码流,0:不禁止，1:禁止访问第0路，2:禁止访问第1路，3：禁止访问第0路，第1路。</VisitStreamOption>
        <DevType>设备类型，100：表示IPC，200：表示NVR</DevType>
    </Device>
    <Device>
        .
        .
        .
    <Device>
    .
    .
    .
</DeviceList>
************************************************************************************************************************/

/************************************************************************************************************************
 *                                        xml 报警器设备列表以及告警数据格式定义说明                                           *
 *************************************************************************************************************************／
 
 //报警器设备列表
 <DevId>摄像机id</DevId>
 <ALERTOR_LIST>
 <ALERTOR ADDR_CODE=4 ALIAS="烟感_门口" ENABLE=1 />
 <ALERTOR ADDR_CODE=5 ENABLE=1 />
           .
           .
           .
 </ALERTOR_LIST>
 
 
 附注：DevId:摄像机ID
      ADDR_CODE : 告警器地址码
      ALIAS ：告警器别名，没有或者为空（用户未设置别名）
      ENABLE：布撤防标志， 1为布防， 0为撤防
 
 //报警器产生的告警消息
 <ALARM ID=5 DEV_TYPE=2 DEV_ADDR=4 EVENT_TYPE=1 DEV_ALIAS="门磁" DEV_SECURITY=1 />
 
 附注：ID ：告警ID唯一标识此告警
      DEV_TYPE:告警器设备类型， 1为门磁，2为烟感 3为燃气
      EVENT_TYPE:告警事件类型， 1为普通告警，2低压告警，3心跳告警
      DEV_ALIAS:告警器别名，如果没设置则没有
      DEV_SECURITY:布防状态
 ************************************************************************************************************************/


/************************************************************************************************************************
 *                                              消息与结构定义说明                                                         *
 ************************************************************************************************************************/
#define TPS_IPC         (100)   //IPC
#define TPS_IPC_WIFI    (101)   //WiFi IPC
#define TPS_NVR_V1      (200)   //NVR 1.0
#define TPS_NVR_V4      (201)   //NVR 4.0

#define DEFAULT_NOT_SPECIFY_CHANNEL (-1)

typedef struct
{
    unsigned int userManagerRight;//用户管理
    unsigned int puManagerRight;//设备管理
    unsigned int videoSuvRight;//视频浏览
    unsigned int ptzSetRight;//云镜控制
    unsigned int alarmManagerRight;//告警管理
    unsigned int videoPalybackRight;//录像回放
    unsigned int conManagerRight;//内容管理
    unsigned int conDeleteRight;//内容删除
    unsigned int tvwallManagerRight;//电视墙
    unsigned int audioTwoWayRight;//语音对讲
    unsigned int audioBrardCastRight;//语音广播
    unsigned int nUserPriority;//用户优先级
    unsigned int showSpeedTest;//网络测试
}UserRight;

#define VS_DEV_SN_LEN  (32)
#define VS_DEV_ID_LEN  (32)
#define VS_DEV_CHN_LEN (64)
#define VS_BIND_USER_LEN (64)
#define MAX_VIDEO_AUDIO_CODEC_LEN (32)
//视频解码参数
typedef struct
{
    unsigned int    stream_index;
    char            video_encoder[MAX_VIDEO_AUDIO_CODEC_LEN];
    unsigned int    width;
    unsigned int    height;
    unsigned int    framerate;
    unsigned int    intraframerate;  //I frame interval
    unsigned int    bitrate;
    char            config[256]; //提交给解码器的第一个I帧前面必须加上config的数据
    int             config_len; //MPEG4 18字节VOL，H264 114字节
}TPS_VIDEO_PARAM;

//音频解码参数
typedef struct
{
    unsigned int     stream_index;
    char             audio_encoder[MAX_VIDEO_AUDIO_CODEC_LEN];
    unsigned int     samplerate;
    unsigned int     samplebitswitdh; //8 or 16
    unsigned int     channels; //0: mono, 1: stero
    unsigned int     bitrate;
    unsigned int     framerate;
}TPS_AUDIO_PARAM;
 
#define MP4FILE_HANDLE void *

#define MAX_USER_NAME_LEN  64
typedef enum
{
    TPS_ACCOUNT_STATUS_NORMAL, //0代表账号状态正常
    TPS_ACCOUNT_STATUS_FROZEN, //1为冻结状态[不能登录]
    TPS_ACCOUNT_STATUS_LOCKED, //2为锁定状态[短期内不能登录]
    TPS_ACCOUNT_STATUS_ABNORMAL, //3为异常状态[可能存在异常行为]
}TPS_ACCOUNT_STATUS;

typedef enum {
    PLATFORM_BIND_NONE,     //0-未绑定
    PLATFORM_BIND_WECHAT,   //1-微信
    PLATFORM_BIND_WEBO,     //2-微博
    PLATFORM_BIND_FACEBOOK, //3-Facebook
    PLATFORM_BIND_LINE,      //4-Line
    PLATFORM_BIND_GOOGLE,    //5-google
    PLATFORM_BIND_APPLE      //6-apple
}PLATFORM_BIND_TYPE;

typedef enum {
    USER_TYPE_NORMAL = 1000,     //普通用户
    USER_TYPE_ENGINEER = 1100,   //工程商用户
}USER_TYPE;

#define MAX_EMAIL_MOBILE_LEN 32
#define MAX_PLATFORM_LENGTH 256
typedef struct
{
    char userName[MAX_USER_NAME_LEN];
    char userId[MAX_USER_NAME_LEN];
    int isModify;
    TPS_ACCOUNT_STATUS accountStatus;
    int isBindEmail; //是否绑定邮箱
    char email[MAX_EMAIL_MOBILE_LEN]; //绑定的邮箱
    int isBindMobile; //是否绑定手机
    char mobile[MAX_EMAIL_MOBILE_LEN]; //绑定的手机
    int isBindWachat; //是否绑定微信
    PLATFORM_BIND_TYPE platformType;//绑定的三方登录类型
    int isForeign;//是否为国外用户；0：否，1：是
    char openPlatformCode[MAX_PLATFORM_LENGTH];//三方登录返回的PlatformCode
    USER_TYPE userType;//用户身份类型，1000->普通用户 1100->工程商用户
}TPS_THIRD_USER_INFO;

//回放与直连访问用到的音视频参数结构体
//tcp连接媒体服务器后需要发送的通知消息头结构定义。使用说明：客户端tcp连接上媒体服务器后需要向服务器发送一个通知消息，通知消息头的填写参考下面结构体字段注释 // 
typedef struct __NetSDK_VIDEO_PARAM
{
    char codec[256];
    int width;
    int height;
    int colorbits;
    int framerate;
    int bitrate;
    char vol_data[256];
    int vol_length;
}NetSDK_VIDEO_PARAM;

typedef struct __NetSDK_AUDIO_PARAM
{
    char codec[256];
    int samplerate;
    int bitspersample;
    int channels;
    int framerate;
    int bitrate;
}NetSDK_AUDIO_PARAM;

//tcp连接媒体服务器后需要发送的通知消息头结构定义。使用说明：客户端tcp连接上媒体服务器后需要向服务器发送一个通知消息，通知消息头的填写参考下面结构体字段注释
typedef struct
{
    unsigned int magic;         //填0x69707673。字段说明：此字段为天视通识别字段。
    unsigned int nSvrInst;      //此id通过TPS_AddWachtRsp消息返回的。字段说明：VSS session ID，根据此ID 媒体服务器可找到Client的所有信息。
    unsigned char nDataSrc;     //填0: 表示是客户端连接。
    unsigned char nPacketType;  //填0: 表示是通知消息
    unsigned short nDataLength; //填0：通知消息不需要后续数据包
}TPS_VsTcpPacketHeader;

//媒体数据包头结构定义
typedef struct
{
    unsigned int frame_timestamp; //此帧对应的时间戳，用于音视频同步，一帧中的不同包时间戳相同
    unsigned int keyframe_timestamp; //如果是非I帧，记录其前一I帧的timestamp，如果解码器没有收到前面那个I帧，所有非I帧丢掉丢包不解码
    unsigned short pack_seq; //包序号0-65535，到最大后从0开始
    unsigned short payload_size; //此包中包含有效数据的长度
    unsigned char pack_type; //0x01第一包，0x10最后一包, 0x11第一包也是最后一包，0x00中间包
    unsigned char frame_type; //帧类型1：I帧，0：非I帧
    unsigned char stream_type; //0: video, 1: audio，2：发送报告，3：接收报告，4：打洞包
    unsigned char stream_index;
    unsigned int frame_index;
}TPS_STREAM_PACKET_HEADER;

typedef struct
{
    int     bIsKey;
    double  timestamp;
    int     nChannelId; //通道号从0开始，不区分通道则为DEFAULT_NOT_SPECIFY_CHANNEL(-1)
}TPS_EXT_DATA;

//视频请求后返回的消息通知，nResult＝0表示视频请求成功，客户端根据nVssSvrIP（媒体服务器地址），nTransPro（媒体传输协议）以及对应的端口进行收流。
//如果是tcp媒体传输协议，客户端主动与nMediaSendPort（媒体服务器发流端口）进行主动连接收流，需要注意的是tcp连接后需要向服务器发送TPS_VsTcpPacketHeader通知消息。
//如果是udp媒体传输协议，客户端直接绑定nMediaRecvPort端口进行收流。
//还需要判断是单播还是组播，如果是组播需要加入组播地址端口进行收流。
//客户端收到媒体流后需要根据数据包头TPS_STREAM_PACKET_HEADER信息进行组包，组包后自己解码显示。
typedef struct
{
    char szDevId[VS_DEV_ID_LEN];//设备id
    int  nResult;//请求结果，0表示成功，非零失败
    int  nTransPro;//媒体传输协议，0:udp,1:tcp
    int  nFSM;//1:表示单播，2:表示组播
    int  nMulIp;//组播地址
    int  nMulPort;//组播端口
    int  nMediaType;//媒体类型，0x0001:视频， 0x0100:音频， 0x0101：音视频
    int  nMediaSendPort;//udp：表示服务器发流端口，需要客户端向本端口打洞；tcp：表示tcp服务器端口，由客户端主动连接。
    int  nMediaRecvPort;//udp本地收流端口
    int  nVssSvrIP;//媒体服务器地址
    int  nSvrInst;//VM@该路视频请求服务器保存的session id，tcp连接发送通知消息的时候需要带上。P2P@nvr channelid
    int  nEnableChangeStream;//是否允许通过1062协议切换主子码流
    TPS_VIDEO_PARAM videoParam;//视频解码参数
    TPS_AUDIO_PARAM audioParam;//音频解码参数
}TPS_AddWachtRsp;

#define DEV_FILE_LEN (1024)
typedef struct
{
    char szDevId[VS_DEV_ID_LEN];//设备ID
    char szReplayFile[DEV_FILE_LEN];//请求回放文件名称
    int nVideoSecs;//回放文件时间长度，单位秒
    int  nResult;//请求结果，0表示成功，非0失败
    int  nActionType;//请求动作，如：播放，暂停，快进，快退等，参考REPLAY_IPC_ACTION枚举值
    short  bHaveVideo;//是否带视频参数
    short  bHaveAudio;//是否带音频参数
    NetSDK_VIDEO_PARAM videoParam;//视频参数
    NetSDK_AUDIO_PARAM audioParam;//音频参数
}TPS_ReplayDevFileRsp;

typedef struct
{
    char szDevId[VS_DEV_ID_LEN];//设备id
    int  nResult;//请求结果，0表示成功，非零失败
    int  nTransPro;//媒体传输协议，0:udp,1:tcp
    int  nVssSvrIP;//媒体服务器地址
    int  nMediaSendPort;//udp：表示服务器发流端口，需要客户端向本端口打洞；tcp：表示tcp服务器端口，由客户端主动连接。
    int  nMediaRecvPort;//udp本地收流端口
    int  nSvrInst;//该路视频请求服务器保存的session id，tcp连接发送通知消息的时候需要带上。
    TPS_AUDIO_PARAM audioParam;//音频解码参数
}TPS_TALKRsp;

//媒体数据包头结构定义
typedef struct
{
    unsigned int frame_timestamp; //此帧对应的时间戳，用于音视频同步，一帧中的不同包时间戳相同
    unsigned int keyframe_timestamp; //如果是非I帧，记录其前一I帧的timestamp，如果解码器没有收到前面那个I帧，所有非I帧丢掉丢包不解码
    unsigned short pack_seq; //包序号0-65535，到最大后从0开始
    unsigned short payload_size; //此包中包含有效数据的长度
    unsigned char pack_type; //0x01第一包，0x10最后一包, 0x11第一包也是最后一包，0x00中间包
    unsigned char frame_type; //帧类型1：I帧，0：非I帧
    unsigned char stream_type; //0: video, 1: audio，2：发送报告，3：接收报告，4：打洞包
    unsigned char stream_index;
    unsigned int frame_index;
}UpdPackHead;

typedef struct
{
    unsigned int flag;
    unsigned int data;
    unsigned int frame_index;
    unsigned int keyframe_index;
}VIDEO_FRAME_HEADER;

//消息事件类型定义
enum TPS_MSG_EVENT
{
    TPS_MSG_NOTIFY_LOGIN_OK = TPS_MSG_BASE+1,//登录成功,返回用户权限
    TPS_MSG_NOTIFY_LOGIN_FAILED,//登录失败,返回设备ID
    TPS_MSG_NOTIFY_DEV_DATA,//登录成功后lib库主动返回xml格式设备数据,具体格式请参见上面说明
    TPS_MSG_RSP_ADDWATCH,//视频请求响应，返回TPS_AddWachtRsp
    TPS_MSG_RSP_PTZREQ,//云台请求响应，返回是否请求成功
    TPS_MSG_RSP_TALK,//对讲请求响应，返回TPS_TALKRsp
    TPS_MSG_RSP_TALK_CLOSE,//对讲停止响应， 返回TPS_NotifyInfo
    TPS_MSG_ALARM,//报警消息，返回TPS_AlarmInfo
    TPS_MSG_EVENT,//事件消息, 返回TPS_EventInfo
    TPS_MSG_P2P_CONNECT_OK,//P2P连接成功，返回对应的设备ID
    TPS_MSG_RSP_GET_DEV_PIC,//获取前端设备图片响应，返回TPS_NotifyInfo
    TPS_MSG_P2P_NETTYPE,//IPC device conncet net type
    TPS_MSG_P2P_OFFLINE,//device offline
    TPS_MSG_P2P_NVR_OFFLINE,//NVR device offline
    TPS_MSG_P2P_NVR_CH_OFFLINE,//NVR channel offline
    TPS_MSG_P2P_NVR_CH_ONLINE,//NVR channel online
    TPS_MSG_P2P_NVR_CH_UNCONNECTED,//NVR channel unconnected
    TPS_MSG_P2P_NVR_CH_ABILITY1,//NVR channel ability1
    TPS_MSG_RSP_UPLOAD_FILE,//request upload file response,return TPS_NotifyInfo
    TPS_MSG_RSP_UPLOAD_PROGRESS,//upload file progress, return xml info
    TPS_MSG_RSP_UPLOAD_FAILED,//upload file failed, return xml info
    TPS_MSG_RSP_UPLOAD_OK,//upload file success, return xml info
    TPS_MSG_NOTIFY_AUTH_FAILED,//device authrication failed, return TPS_NotifyInfo
    TPS_MSG_P2P_NVR_CONNECT_REFUSE,////nvr4.0 connect failed, return TPS_NotifyInfo
    TPS_MSG_RSP_SEARCH_NVR_REC,//response search nvr record result,return TPS_NotifyInfo.szInfo contain char "ABCCC...."
    TPS_MSG_RSP_NVR_REPLAY,//nvr replay by time response, return TPS_ReplayDevFileRsp
    TPS_MSG_NOTIFY_DISP_INFO,//notify display info, return TPS_NotifyInfo
    TPS_MSG_NOTIFY_P2P_TCP_TIMEOUT,//response tcp timeout, return TPS_NotifyInfo
    TPS_MSG_RSP_UPDATE_FW_INFO,//response get update firmware info, return xml
    TPS_P2P_NETWORK_QS_INFO,    //network QS info
    TPS_P2P_NOTIFY_SVR_LOGIN_OK,    //p2p server login ok
    TPS_MSG_NOTIFY_BEGIN_RECORD,
    TPS_MSG_NOTIFY_END_RECORD,
    TPS_MSG_NOTIFY_P2P_THREAD_EXIT,
    TPS_MSG_RSP_PLAYSTART_NVR,
    TPS_MSG_RSP_PLAYSEEK_NVR,
    TPS_MSG_RSP_SEARCH_NVR_REC_BYMONTH,//response search nvr record by month result,return TPS_NotifyInfo.szInfo contain char "201709:101010....","201709:" is the time
    TPS_MSG_RSP_QUERY_SHARE_USER_INFO,
    TPS_MSG_RSP_GET_DEVICE_SHARING_CODE,
    TPS_MSG_NOTIFY_BIND_STATUS_DATA,//查询wifi绑定成功状态的消息
    TPS_MSG_NOTIFY_USER_INFO_MODIFY,
    TPS_MSG_NOTIFY_GET_DEVLIST_DEV_INFO,
    TPS_MSG_RSP_NVR_RECORD_DOWNLOAD_START,
    TPS_MSG_RSP_NVR_RECORD_DOWNLOAD_FAILED,
    TPS_MSG_RSP_NVR_RECORD_DOWNLOAD_PROGRESS,
    TPS_MSG_P2P_LOG,
    TPS_MSG_SPEED_TEST,
    TPS_MSG_NOTIFY_LOGIN_AGAIN,//登录状态失效,需要重新登录
    TPS_MSG_NOTIFY_BAD_NETWORK,//与服务器交互时出现网络异常错误
    TPS_MSG_NOTIFY_AUTH_SUCCESS,//device authrication success, return TPS_NotifyInfo
    TPS_MSG_NOTIFY_GET_COMBOINFO,//获取设备套餐使用信息,返回结构体TPS_NotifyInfo，其中szDevId为序列号
    TPS_MSG_NOTIFY_GET_DEVICEQRINFO,//获取设备二维码信息,返回结构体TPS_DeviceQRInfo
    TPS_MSG_NOTIFY_GET_SHARE_AUTH_SET_LIST,//从服务器获取分享权限设置项列表,返回json格式字符串
    TPS_MSG_NOTIFY_GET_SHARING_DEVICE_USER_DETAIL_INFO,//从服务器获取设备分享给用户的详细信息
    TPS_MSG_NOTIFY_MODIFY_SHARING_DEVICE_AUTH,//修改设备分享权限信息
    TPS_MSG_P2P_NVR_CH_PROTOCOL,//NVR channel heartbeat protocol
    TPS_MSG_RSP_SEARCH_NVR_REC_SEC,//查询NVR录像当天回放时间段精确到秒回调
    TPS_MSG_NOTIFY_TECENT_CLOUD_STORAGE_DETAIL,//获取设备的腾讯云存详细信息,返回TPS_NotifyInfo_Ex，其中szDevId为序列号
    TPS_MSG_NOTIFY_TECENT_CLOUD_STORAGE_DATE,//获取腾讯云存服务具有云存的日期,返回TPS_NotifyInfo_Ex，其中szDevId为序列号
    TPS_MSG_NOTIFY_TECENT_CLOUD_STORAGE_TIME,//获取腾讯云存服务具有云存的时间轴,返回TPS_NotifyInfo_Ex，其中szDevId为序列号
    TPS_MSG_NOTIFY_TECENT_CLOUD_STORAGE_EVENTS,//获取腾讯云存服务云存事件列表,返回TPS_NotifyInfo_Ex，其中szDevId为序列号
    TPS_MSG_NOTIFY_TECENT_CLOUD_STORAGE_EVENTS_THUMBNAIL,//获取腾讯云存服务云存事件列表,返回TPS_NotifyInfo_Ex，其中szDevId为序列号
    TPS_MSG_NOTIFY_TECENT_CLOUD_STORAGE_ENCRYPTURL,//获取腾讯云存服务云存事件列表,返回TPS_NotifyInfo_Ex
    TPS_MSG_HAS_SYSTEM_NOTIFY,//服务器侧有需要显示的系统消息
    TPS_MSG_GET_SYSTEM_NOTIFY,//获取服务器侧的系统消息
    TPS_MSG_AJAXADDDEVICE_NOTIFY,//设备添加接口返回xml
    TPS_MSG_NOTIFY_GET_DEVICE_BIND_USERS_LIST,//获取添加设备的用户列表,返回xml
    TPS_MSG_REGISTER_USER_WITH_TOKEN,//本地手机号一键注册返回xml
    TPS_MSG_QUERY_ALL_SHARING_DEVICE_AUTH,//获取所有分享设备权限
    TPS_MSG_GET_PUSH_SCHEME,//获取推送方案
    TPS_MSG_GET_USER_PUSH_CONFIG,//获取用户是否关闭离线推送的配置信息
    TPS_MSG_GET_MSG_LIST,//获取用户消息列表
    TPS_MSG_GET_MSG_UNREAD_COUNT,//获取未读消息数量
    TPS_MSG_RSP_CHANGE_STREAM,//切换预览主子码流响应，返回TPS_AddWachtRsp
    TPS_MSG_P2P_NVR_CH_FEATURE, //NVR通道feature，回调内容为TPS_NotifyInfo
    TPS_MSG_P2P_NVR_CH_BIND_INFO, //NVR通道绑定关系，回调内容为TPS_NotifyInfo
    TPS_MSG_RSP_TRUSTED_DEV_LIST, //托管设备列表，回调内容为json字符串
    TPS_MSG_RSP_TRUSTED_DEV_DETAIL, //托管设备详情，回调内容为json字符串
    TPS_MSG_NOTIFY_TRACK_POINT,//埋点信息，回调内容为TPS_NotifyInfo
    TPS_MSG_NEW_USER_TOKEN, //回调最新的accessToken信息，回调内容为json字符串
    TPS_MSG_RSP_ALARM_IMG_DATA,//报警图片数据
    TPS_MSG_RSP_UPLOAD_LOG_FILE,//上传日志文件
};

//seetong服务器接口公用错误码
enum server_request_error{
    server_request_error_no = 200, //请求成功
    server_request_error_app_need_upgrade = -99999999, //APP需要升级版本
    server_request_error_user_not_login = -99999998, //用户未登录
    error_accesstoken_invalid = 10040102, //accesstoken无效，无法解析或验签失败，需要刷新accesstoken
    error_accesstoken_expired = 10040103, //accesstoken验签通过，但已过期，需要刷新accesstoken
    error_refreshtoken_invalid = 10040111, //refreshtoken无效，无法解析或验签失败，需重新登录。
    error_refreshtoken_expired = 10040112, //refreshtoken验签通过，但已过期，需重新登录。
    error_passsword_be_modify = 10040113, //用户已修改密码，请重新登录
    error_need_switch_back_server = 10050301, //服务不可用，需要切换到备用域名
};

typedef struct
{
    char szDevId[VS_DEV_ID_LEN];
    int  nResult;
    char szInfo[1444];
}TPS_NotifyInfo;

typedef struct
{
    char szDevId[VS_DEV_ID_LEN];
    int  nResult;
    int nInfoLength;
    char szCallFlag[256];
    char szInfo[]; //柔性数组
}TPS_NotifyInfo_Ex;

//告警类型定义
enum TPS_ALARM_TYPE
{
    TPS_ALARM_NONE = 0,
    TPS_ALARM_FIRE,//火警
    TPS_ALARM_SMOKE,//烟警
    TPS_ALARM_INFRARED,//红外报警
    TPS_ALARM_GAS,//气体报警
    TPS_ALARM_TEMPERATURE,//温度报警
    TPS_ALARM_GATING,//门控报警
    TPS_ALARM_MANUAL,//手动报警
    TPS_ALARM_FRAME_LOST,//视频丢失报警
    TPS_ALARM_MOTION,//移动侦测报警
    TPS_ALARM_MASKED,//视频遮挡报警
    
    TPS_ALARM_LINKDOWN = 21,//设备掉线
    TPS_ALARM_LINKUP,//设备上线
    TPS_ALARM_USB_PLUG,//USB插上
    TPS_ALARM_USB_UNPLUG,//USB拔掉
    TPS_ALARM_SD0_PLUG,//SD1插上
    TPS_ALARM_SD0_UNPLUG,//SD1拔掉
    TPS_ALARM_SD1_PLUG,//SD2插上
    TPS_ALARM_SD1_UNPLUG,//SD2拔掉
    TPS_ALARM_USB_FREESPACE_LOW,//USB空间不足
    TPS_ALARM_SD0_FREESPACE_LOW,//SD1卡空间不足
    TPS_ALARM_SD1_FREESPACE_LOW,//SD2卡空间不足
    TPS_ALARM_VIDEO_LOST,//视频丢失
    TPS_ALARM_VIDEO_COVERD,//视频遮挡
    TPS_ALARM_MOTION_DETECT,//移动侦测
    TPS_ALARM_GPIO3_HIGH2LOW,//告警输入高变低
    TPS_ALARM_GPIO3_LOW2HIGH,//告警输入低变高
    TPS_ALARM_STORAGE_FREESPACE_LOW,//存储空间不足
    TPS_ALARM_RECORD_START,//录像开始
    TPS_ALARM_RECORD_FINISHED,//录像结束
    TPS_ALARM_RECORD_FAILED,//录像失败
    ALARM_CODE_INPUT_ALARM_ON,
    ALARM_CODE_INPUT_ALARM_OFF,
    TPS_ALARM_GPS_INFO,//GPS信息
    TPS_ALARM_EMERGENCY_CALL,//紧急呼叫
    TPS_ALARM_JPEG_CAPTURED,//控制前端抓图报警
    TPS_ALARM_RS485_DATA, //前端串口数据报警
    TPS_ALARM_SAME_IP, //IP地址冲突
    
    TPS_ALARM_TST_NO = 60,//无异常
    TPS_ALARM_TST_DISKFULL,//硬盘满
    TPS_ALARM_TST_DISKERROR,//硬盘错误
    TPS_ALARM_TST_SD_CARD_ERROR,//SD异常
    TPS_ALARM_TST_IPCONFLICT,//IP冲突
    TPS_ALARM_TST_ILLEGEACCESS,//非法访问
    TPS_ALARM_TST_VIDEOSTANDARDEXCEPTION,//制式异常
    TPS_ALARM_TST_VIDEOEXCEPTION,//视频异常
    TPS_ALARM_TST_ENCODEERROR,//编码异常
    TPS_ALARM_TST_TST_NO,//无报警
    TPS_ALARM_TST_TST_IN,//报警输入
    TPS_ALARM_TST_TST_MOTION,//移动侦测
    TPS_ALARM_TST_TST_VIDEOLOSS,//视频丢失
    TPS_ALARM_TST_TST_EXCEPION,//异常报警
    TPS_ALARM_TST_TST_MASK,//遮挡检测
    ALARM_TST_IOALARM_ON, //IO报警开始
    ALARM_TST_IOALARM_OFF, //IO报警结束
    TPS_ALARM_TST_TST_DISKGROUP_ERROR, //盘组异常 77
    ALARM_TST_REGIONAL_ON,      //区域入侵
    ALARM_TST_REGIONAL_OFF,     //区域入侵清除
    ALARM_TST_CROSSBORDER_ON,   //越界侦测
    ALARM_TST_CROSSBORDER_OFF,  //越界侦测清除
    ALARM_TST_HUMANFORM_ON,     //人形识别
    ALARM_TST_HUMANFORM_OFF,    //人形识别清除
    ALARM_TST_HUMANFACE_ON,     //人脸识别
    ALARM_TST_HUMANFACE_OFF,    //人脸识别清除
    ALARM_TST_LICENSEPLATE_ON,  //车牌识别
    ALARM_TST_LICENSEPLATE_OFF, //车牌识别清除
    ALARM_TST_VEHICLETYPE_ON,   //车型识别
    ALARM_TST_VEHICLETYPE_OFF,  //车型识别清除
    ALARM_TST_ANIMALDETEC_ON,   //动物识别触发
    ALARM_TST_ANIMALDETEC_OFF,  //动物识别清除
    ALARM_TST_TUMBLE_ON,    //跌倒识别触发//32
    ALARM_TST_TUMBLE_OFF,   //跌倒识别清除
    ALARM_TST_PARABOLICDETEC_ON,    //高空抛物触发//34
    ALARM_TST_PARABOLICDETEC_OFF,   //高空抛物清除

    ALARM_TST_CHANNEL_OFFLINE = 104, //通道掉线
};

typedef struct
{
    char szDevId[VS_DEV_ID_LEN];//设备ID
    unsigned int nTimestamp;//报警时间
    unsigned int nType;//报警类型
    unsigned int nIsRaise;//报警状态，产生 or 消失
    unsigned int nAlarmLevel;//报警级别
    char szDesc[128];//报警描述
    int nChannelId;
    int nSrc;//-1表示ipc发的  0表示nvr自己发的  1表示nvr转发ipc的
}TPS_AlarmInfo;

//事件类型定义
enum TPS_EVENT_TYPE
{
    TPS_EVENT_NONE = 0,
    TPS_EVENT_USB_PLUGIN,//U盘插入
    TPS_EVENT_USB_UNPLUG,//U盘拔出
    TPS_EVENT_SD1_PLUGIN,//SD1插入
    TPS_EVENT_SD1_UNPLUG,//SD1拔出
    TPS_EVENT_SD2_PLUGIN,//SD2插入
    TPS_EVENT_SD2_UNPLUG,//SD2拔出
    TPS_EVENT_RECORD_START,//录像开始
    TPS_EVENT_RECORD_FINISHED,//录像结束
    TPS_EVENT_RECORD_FILE_REMOVED,//录像文件删除
    TPS_EVENT_RECORD_DIR_REMOVED,//录像目录删除
    TPS_EVENT_START_UPDATE_FIRMWARE,//固件更新
    TPS_EVENT_UPDATE_FIRMWARE_OK,//固件更新成功
    TPS_EVENT_UPDATE_FIRMWARE_FAILED,//固件更新失败
    TPS_EVENT_UPDATE_CONFIG_OK,//配置更新
    TPS_EVENT_UPDATE_CONFIG_FAILED,//配置更新失败
    TPS_EVENT_REBOOT,//重启
    TPS_EVENT_GPS_INFO,//GPS信息
    TPS_EVENT_OTHER//其他
};

typedef struct
{
    char szDevId[VS_DEV_ID_LEN];//设备ID
    unsigned int nTimestamp;//事件时间
    unsigned int nType;//事件类型
    char szDec[128];//事件描述
}TPS_EventInfo;

enum TPS_ERR_NUM
{
    ERR_NONE = 0,
    ERR_OUTOFF_MEMORY = -100,           //申请内存失败  
    ERR_INVALID_ADDR = -101,            //服务器地址错误  
    ERR_SOCKET = -102,                  //网络异常  
    ERR_NOT_FIND_DEV = -103,            //未找到此设备  
    ERR_DEV_LOCK = -104,                //设备被锁定  
    ERR_USER_PASSWORD = -105,           //用户名，密码错误  
    ERR_RTSP_REALPLAY = -106,           //RTSP播放失败  
    ERR_RTSP_STOPPLAY = -107,           //RTSP停止失败  
    ERR_INVALID_XML = -108,             //XML数据错误  
    ERR_P2P_SVR_LOGIN_FAILED = -109,    //播放失败,P2P服务器登录失败  
    ERR_P2P_DISCONNECTED = -110,        //播放请求中，正在建立P2P连接   
    ERR_P2P_AUTH_FAILED = -111,         //播放失败，P2P设备认证失败  
    ERR_UPNP_DISCONNECT = -112,         //播放失败， UPNP设备连接失败  
    ERR_UPNP_DEV_AUTH_FAILED = -113,    //播放失败， UPNP设备认证失败  
    ERR_PLAY_FAILED = -114,             //播放失败，未知错误请重新播放  
    ERR_AUDIO_NOT_START = -115,         //对讲没启动  
    ERR_AUTHCODE_NULL = -116,           //请求参数Authcode为空  
    ERR_INVALID_SESSION = -117,         //用户登陆session无效  
    ERR_INVALID_RANDOM_DATA =-118,      //随机数失效  
    ERR_RSP_TIMEOUT = -119,             //响应超时  
    ERR_P2P_DEV_NOT_ALLOW_REPLAY = -120,//设备不支持前端回放  
    ERR_NVR_CHANNEL_OFFLINE = -121,     //nvr channel is offline
    ERR_USER_NOT_FIND = -122,           //用户不存在  
    ERR_UNKOWN = -200,                  // 未知错误 
    ERR_NO_INIT_LIB = -201,             //没有初始化库
    ERR_INVALID_PARAMETER = -202,       //无效的参数
    ERR_USER_NOT_LOGIN = -203,          //用户没有登陆
    ERR_LIB_FREE = -204,                //库被释放了
    ERR_BUFFER_IS_SMALL = -205,         //buffer空间太小
    ERR_DATA_FORMAT_ERROR = -206,       //数据格式化错误
    ERR_SAVE_DATA_FAILED = -207,        //保存数据失败
    ERR_NO_MORE_DATA = -208,            //没有更多的数据
    ERR_PAR_NO_CARRY_ENC_NUM = -209,    //参数错误，没有携带加密数
    ERR_NOT_GET_RANDOM_DATA = -210,      //没有获取随机数
    ERR_ILLEGAL_RANDOM_DATA = -211,      //非法随机数
    ERR_DECRYPTION_DATA_FAILURE = -212, //加解密数据失败
    ERR_NO_LOGIN_WECHAT = -213,         //不是微信登录
    ERR_INVALID_CODE_TOKEN = -214,      //通过code获取的token失效
    ERR_INVALID_UNIONID = -215,         //无效unionid无效
    ERR_CONNECT_DATABASE_FAILURE = -216,//连接数据库失败
    ERR_WECHAT_RELATE_USER_FAILURE = -217,//微信关联用户失败
    ERR_WECHAT_RELATE_USER_TYPE_ERROR = -218,//微信关联用户类型错误
    ERR_ILLEGAL_USERNAME_OR_PASSWORD = -219,//非法用户名或密码
    ERR_WECHAT_NOT_BIND_USER = -220,    //微信号未绑定用户
    ERR_USERNAME_NOT_MODIFY = -221,     //用户名不能修改
    ERR_USERNAME_ALREADY_USED = -222,     //用户名已经被使用
    ERR_NO_RIGHT_CALL_FUNCTION = -223,    //没有权限调用此接口函数(SDK定制用)
    ERR_NVR_CHANNEL_UNCONNECTED = -224,   //此NVR通道未连接
    ERR_WECHAT_ACCOUNT_FROZEN = -225,     //微信账号被冻结,对账号封停存在异议，可以提交申诉，三个月内未申诉将注销账号
    ERR_USER_ACCOUNT_FROZEN = -226,       //账号被冻结,对账号封停存在异议，可以提交申诉，三个月内未申诉将注销账号
    ERR_USER_ACCOUNT_LOCKED = -227,       //账号被锁定,用户登录输入错误密码次数过多，账号被锁定当天不能登录
    ERR_VERSION_STOPED = -228,       //版本已停止维护，请前往官网下载最新版本，官网：点击进入官网 （http://www.tpsee.com）
};

//音频对讲数据
typedef struct
{
    int len;
    unsigned int frame_timestamp;//此帧对应的时间戳，用于音视频同步，一帧中的不同包时间戳相同
    unsigned short pack_seq;//包序号-65535，到最大后从开始
    unsigned int  frame_index; //新增加字段
    char * pBuffer;
}TPS_AudioData;

//设备二维码信息
typedef struct
{
    char szDevSN[VS_DEV_SN_LEN];//设备SN
    char szDevId[VS_DEV_ID_LEN];//设备云ID
    int nType;//设备类型
    int nSubType;//设备子类型
    int nIsOnline;//设备是否在线
    int nRetValue;//接口返回值
    char szBindUser[VS_BIND_USER_LEN];//绑定用户
    long nFeature;//设备特征值
}TPS_DeviceQRInfo;

typedef struct {
    char szDevId[VS_DEV_ID_LEN];
    char szEventTime[VS_DEV_ID_LEN];
    int dataSize;
    int startPos;
} TPS_ALARM_IMG_DATA;

//云台控制枚举
enum PTZ_CMD_TYPE
{
    LIGHT_PWRON = 2,// 2 接通灯光电源
    WIPER_PWRON,// 3 接通雨刷开关
    FAN_PWRON,// 4 接通风扇开关
    HEATER_PWRON,// 5 接通加热器开关
    AUX_PWRON1,// 6 接通辅助设备开关
    AUX_PWRON2,// 7 接通辅助设备开关
    ZOOM_IN_VALUE = 11,// 焦距变大
    ZOOM_OUT_VALUE, //12 焦距变小
    FOCUS_NEAR, //13 焦点前调
    FOCUS_FAR, //14 焦点后调
    IRIS_OPEN, //15 光圈扩大
    IRIS_CLOSE,// 16 光圈缩小
    TILT_UP,// 17 云台上
    TILT_DOWN, //18 云台下
    PAN_LEFT,// 19 云台左
    PAN_RIGHT,// 20 云台右
    UP_LEFT,// 21 云台左上
    UP_RIGHT,// 22 云台右上
    DOWN_LEFT, //23 云台左下
    DOWN_RIGHT,//24 云台右下
    PAN_AUTO,//25 云台自动
    STOPACTION//26 停止
};

enum
{
    error_no = 0,
    error_invalid_ip,
    error_socket_init,
    error_socket_create,
    error_socket_set_recv_buf,
    error_socket_connect_delay,
    error_socket_send_fail,
    error_socket_read_delay,
    error_socket_recv_fail,
    error_no_recv_xml,
    error_out_buffer_too_small,
    error_out_buffer_invalid,
    error_dev_sn,
    error_invalid_username_or_password
};

enum IOT_BIND_TYPE
{
    IOT_BIND_AP = 0,    //AP热点绑定
    IOT_BIND_QRCODE,    //二维码扫码绑定
};

enum TPS_DEVICE_ONLINE_STATUS
{
    TPS_DEVICE_STATUS_OFFLINE = 0,        // 离线
    TPS_DEVICE_STATUS_ONLINE = 1,         // 在线
    TPS_DEVICE_STATUS_UNCONNECTED = 2,    // 未连接
    TPS_DEVICE_STATUS_MAX
};

enum SDK_INIT_NET
{
    SDK_INIT_NET_ONLINE = 0, //使用线上域名app.seeetong.com
    SDK_INIT_NET_LOC = 6, //本地直连设备方式不需要解析服务器域名
    SDK_INIT_NET_TEST = 99 //使用测试环境域名test.seetong.com
};

// 上传到设备中文件类型
typedef enum
{
    FILE_TYPE_CONFIG=0,//配置文件
    FILE_TYPE_FIRMWARE=1,//固件
    FILE_TYPE_AUDIO=2,//音频文件
    FILE_TYPE_COMPRESS_CONFIG=3,//配置文件压缩包
    FILE_TYPE_LOGO=4,//局域网为，设备开机logo；p2p：为人脸特征yuv导入(但已经不用了)
    FILE_TYPE_AI_ALGORITHM=8,//AI算法
    FILE_TYPE_BLE_TEST=9,//蓝牙产测文件
}UPLOAD_FILE_TYPE;

#define MAX_LEN_32 32
#define MAX_LEN_64 64

#define HTTP_HEADER_AUTH "c2VldG9uZ19jbG91ZF9tZW1iZXI6c2VldG9uZ19jbG91ZF9tZW1iZXJfc2VjcmV0"//http头部固定值
#define USER_LOGIN_PATH "/seetong-member-auth/oauth/token" //登录接口
#define USER_LOGOUT_PATH "/seetong-member-auth/logout" //退出登录
#define DEV_P2P_LIST_PATH "/seetong-member-device/device/p2p/list" //获取p2p服务器列表
typedef void (*fcLogCallBack)(unsigned int uLevel, const char* lpszOut);
typedef int (*MsgRspCallBack)(unsigned int nMsgType, char* pData, unsigned int nDataLen, void *pExtData, unsigned int nExtDataLen);
typedef int (*MediaRecvCallBack)(char* pDevId, unsigned int nMediaType, unsigned char* pFrameData, unsigned int nDataLen, TPS_EXT_DATA *pExtData);


/*************************************************************************************************************************
*                                             功能接口函数与说明                                                            *
**************************************************************************************************************************/
/*
 函数名称：FC_init
 函数功能：初始化库接口
 参数说明：空
 返回值：0：成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_init();

/*
 函数名称：FC_initEx
 函数功能：初始化库接口，不可以在回调线程中直接调用，会造成死锁
 参数说明：nNetType:网络类型，0表示WIFI/4G，1表示3G, 2表示2G
 返回值：0：成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_initEx(int nNetType);

/*
 函数名称：FC_initWithDomain
 函数功能：初始化库接口，不可以在回调线程中直接调用，会造成死锁
 参数说明：domain:主服务器域名 fwUpdateDomain:固件升级服务器域名
 返回值：0：成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_initWithDomain(const char *domain, const char *fwUpdateDomain);

typedef struct {
    char os[MAX_LEN_32];
    char lang[MAX_LEN_32];
    char brand[MAX_LEN_32];
    char type[MAX_LEN_32];
    char name[MAX_LEN_32];
    char version[MAX_LEN_32];
    char clientId[MAX_LEN_64];
    char userDomain[MAX_LEN_64];
    char userDomainBack[MAX_LEN_64];
} HttpHeader;

FUNCLIB_LIBRARY int FC_initWithHeader(HttpHeader *header);

/*
 函数名称：FC_initEX_SSL
 函数功能：重新初始化SSL的连接 
 参数说明：0 : seetong.com  1:www.seetong.com 
 返回值：0:成功，非0:失败
*/
FUNCLIB_LIBRARY int FC_initEX_SSL(int nDomianType);

/*
 函数名称：FC_Free
 函数功能：释放库接口
 参数说明：空
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Free();

/*
 函数名称：FC_SetfcLogCallBack
 函数功能：设置日志回调函数，用来接收库返回的日志
 参数说明：回调函数
 返回值：0:成功，非0:失败
 */

FUNCLIB_LIBRARY int FC_SetfcLogCallBack(fcLogCallBack fMsgRspCallBack);
FUNCLIB_LIBRARY int FC_SetfcLogCallBackEx(fcLogCallBack fMsgRspCallBack,int nLevel);
FUNCLIB_LIBRARY int FC_SetfcLogPutAddr(const char *addr, int port);
FUNCLIB_LIBRARY int FC_Log(int level, const char *msg);

/*
 函数名称：FC_PostNetLogForRetpwd
 函数功能：NVR密码找回的APP二维码扫描行为上传LOG服务器记录
 参数说明：pEvent："TEST"或"RETPWD"；pDevId：设备云ID；pDevSN：设备序列号；
 指定事件为"TEST"用于确认与LOG服务器的连通性，指定事件为"RETPWD"才是最终将扫描行为上传LOG服务器记录
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_PostNetLogForRetpwd(const char* pEvent, const char* pDevId, const char* pDevSN);

/*
 函数名称：FC_PostUserLog
 函数功能：把日志上传服务器
 参数说明：pLogInfo:日志信息, pAppVersion:APP版本(如:IOS6.2.1), logType:日志类型(FC_USER_LOG_E枚举)
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_PostUserLog(const char *pLogInfo, const char* pAppVersion, int logType);

/*
 函数名称：FC_SetMsgRspCallBack
 函数功能：设置回调函数，用来接收库返回的消息通知和数据
 参数说明：回调函数
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_SetMsgRspCallBack(MsgRspCallBack fMsgRspCallBack);

/*
 函数名称：FC_SetMediaRecvCallBack
 函数功能：设置回调函数，用来接收媒体数据
 参数说明：回调函数
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_SetMediaRecvCallBack(MediaRecvCallBack fMediaRecvCallBack);

/*
 函数名称：FC_RefreshDevInfo
 函数功能：刷新设备列表
 参数说明：
 返回值：0：成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_RefreshDevInfo();
    
/*
 函数名称：FC_LoginByThirdSoft
 函数功能：通过第三方账号登录，例如微信登录
 参数说明：pType：登录类型，如“wechat”:微信登录，"line":line登录，；pClient：客户端为”client“ app为“app”；pCode：第三方软件生成的code；pAppName：app名称；pAppVersion：app版本号
 返回值：0：成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_LoginByThirdSoft(const char* pType, const char* pClient, char* pCode, const char* pAppName, const char* pAppVersion, char *pPushInfo, char *pEventId);

/*
 函数名称：FC_ModifyThirdLoginUserName
 函数功能：通过第三方账号登录，例如微信登录,修改服务器随机分配的用户名一次
 参数说明：pUserName：原用户名，入“wechat”；pPwd:密码
 返回值：0：成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_ModifyThirdLoginUserName(const char* pUserName, char* pPwd);

/*
 函数名称：FC_ModifyThirdLoginPassword
 函数功能：通过第三方账号登录，例如微信登录，修改密码时不需要验证旧密码
 参数说明：pUserName：用户名，pPwd：新密码
 返回值：
 */
enum {
    modify_pwd_null = 0,            //0:修改成功
    modify_pwd_user_not_login,      //-2125001:用户未登陆
    modify_pwd_parameter_invalid,   //-2125002:非法的用户名或密码
    modify_pwd_not_third_login,     //-2125003:用户类型错误(不是通过微信登录)
    modify_pwd_database_error,      //-2125004:连接数据库失败
    modify_pwd_user_not_exist,      //-2125005:用户不存在
    modify_pwd_other,               //-2125007:其他错误
};
FUNCLIB_LIBRARY int FC_ModifyThirdLoginPassword(const char* pUserName, const char* pPwd);

/*
 函数名称：FC_Login
 函数功能：登陆服务器
 参数说明：pUserName：登陆用户名；pPwd：登陆密码；pVmsIp：服务器地址；nVmsPort：服务器端口
 返回值：0：成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Login(const char* pUserName, const char* pPwd, const char* pVmsIp, unsigned short nVmsPort,char* appVersion, char *pPushInfo, const char *pEventId);

/*
 函数名称：FC_GetPushScheme
 函数功能：获取离线推送方案接口
 参数说明：requestBody 使用json字符串，内容如下
 {
     "phoneBrand": "iphone",
     "phoneType": "MagicUI_5.0.0",
     "firmPush": 0,
     "pushSdk": ["apns", "hw", "xm"],
     "appVersion": "1.3.5",  //APP版本  新增字段
     "systemNotification":0  //系统通知状态 0->关闭，1->开启    新增字段
 }

 返回值：200：成功，非200:失败
 回调消息：TPS_MSG_GET_PUSH_SCHEME
 */
FUNCLIB_LIBRARY int FC_GetPushScheme(const char *requestBody);


/*
 函数名称：FC_AddPushRelation
 函数功能：上报用户离线推送token信息接口
 参数说明：requestBody 使用json字符串，内容如下
 {
     "pushServer": "hw",
     "operateSystem": "ios",
     "language": "zh",
     "env": "seetong",
     "token": "AJDIMEK54ADS44ASD48AW4DA31D4A"
 }

 返回值：200：成功，非200:失败
 */
FUNCLIB_LIBRARY int FC_AddPushRelation(const char *requestBody);

/*
 函数名称：FC_DelPushRelation
 函数功能：删除用户离线推送token信息接口
 参数说明：requestBody 使用json字符串，内容如下
 {
    "pushToken":""
 }

 返回值：200：成功，非200:失败
 */
FUNCLIB_LIBRARY int FC_DelPushRelation(const char *requestBody);

/*
 函数名称：FC_UpdateUserPushConfig
 函数功能：上报用户是否关闭离线推送的配置信息接口
 参数说明：requestBody 使用json字符串，内容如下
 {
     "switch": 1,
 }

 返回值：200：成功，非200:失败
 */
FUNCLIB_LIBRARY int FC_UpdateUserPushConfig(const char *requestBody);

/*
 函数名称：FC_GetUserPushConfig
 函数功能：获取离线推送配置信息接口
 参数说明：无
 返回值：200：成功，非200:失败
 回调消息：TPS_MSG_GET_USER_PUSH_CONFIG
 */
FUNCLIB_LIBRARY int FC_GetUserPushConfig();

/*
 函数名称：FC_LoginDev();
 函数功能：通过设备ID, 设备登录账号, 设备登录密码, 访问token登录设备;
 参数说明：pDevId 设备ID pAccount 设备登录账号 pPassword 设备登录密码 access_token 访问token;
 返回值：0：成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_LoginDev(const char *pDevId, const char *pAccount, const char *pPassword, const char *pAccessToken);

/*
 函数名称：FC_Logout
 函数功能：注销登录，不可以在回调线程中直接调用，会造成死锁
 参数说明：空
 返回值：0:成功；非0:失败
 */
FUNCLIB_LIBRARY int FC_Logout();

/*
 函数名称：FC_AddWatch
 函数功能：请求某设备视频流
 参数说明：pDevId：设备id；nStreamNo：请求该设备的哪一路流,0:主码流，1:子码流; nFrameType:0表示请求播放所有视频帧，1表示只请求播放关键帧; nAudioEnable:步请求音频流 1请求音频流
 返回值：0:成功；非0:失败
*/
FUNCLIB_LIBRARY int FC_AddWatch(char* pDevId, int nStreamNo, int nFrameType, int nAudioEnable);

/*
Function Name: FC_AddWatchEx();
Description: Get one device stream, can select communication mode;
Parameters: pDevId@device id; nStreamNo@stream type, 0:main-stream,1:sub-stream; nFrameType@0:get all video frame,1:only get key frame; nComType@select communication type, 0:by p2p, 1:by cloud relay;
Return: 0:success; !=0:failed;
 */
FUNCLIB_LIBRARY int FC_AddWatchEx(const char* pDevId, int nStreamNo, int nFrameType, int nComType, int nAudioEnable);

/*
 函数名称：FC_StopWatch
 函数功能：停止某设备视频流
 参数说明：pDevId：设备id
 返回值：0:成功；非0:失败
 */
FUNCLIB_LIBRARY int FC_StopWatch(char* pDevId);

/*
 函数名称：FC_StartRecord
 函数功能：开始录像
 参数说明：pDevId：设备id; pFilePath:录像文件存储路径(注意如果传入的是.mp4结尾的路径文件则只生成此文件，不会自动切片); nFileMaxSeconds:单个录像文件时长，单位为秒
 返回值：0:成功；非0:失败
 */
FUNCLIB_LIBRARY int FC_StartRecord(char* pDevId, char *pFilePath, int nFileMaxSeconds);

/*
 函数名称：FC_StopRecord
 函数功能：停止录像
 参数说明：pDevId：设备id
 返回值：0:成功；非0:失败
 */
FUNCLIB_LIBRARY int FC_StopRecord(char* pDevId);

/*
 函数名称：FC_PTZAction
 函数功能：云台控制
 参数说明：pDevId：设备id;pPtzCmd:云台控制命令，具体命令请参考文档说明
 返回值：0:函数调用成功；非0:失败
 说明：此接口由用户自己编写云台控制命令传入是方便用户传输自己是私有数据
 */
FUNCLIB_LIBRARY int FC_PTZAction(char* pDevId, char* pPtzCmd);

/*
 函数名称：FC_PTZActionWithPte
 函数功能：云台控制
 参数说明：pDevId：设备id;pPtzCmd:云台控制命令，具体命令请参考文档说明;nTransChannel：透明通道号
 返回值：0:函数调用成功；非0:失败
 说明：此接口由用户自己编写云台控制命令传入是方便用户传输自己是私有数据
 */
FUNCLIB_LIBRARY int FC_PTZActionWithPte(char* pDevId, char* pPtzCmd, int nTransChannel);

/*
 函数名称：FC_PTZAction
 函数功能：云台控制
 参数说明：pDevId：设备id;nPTZConmand:云台控制命令，参考枚举值，nPSpeed：水平速度；nTspeed：垂直速度
 返回值：0:函数调用成功；非0:失败
 */
FUNCLIB_LIBRARY int FC_PTZActionEx(char *pDevId, int nPTZConmand, int nPSpeed, int nTspeed);

/*
 函数名称：FC_StartTalk
 函数功能：请求对讲
 参数说明：pDevId：设备id；bCaptureAudio：是否由SDK内部直接采集音频，如果外面自行采集编码则调用FC_InputAudioData输入。 bTowWayCall：是否双向通话
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_StartTalkEx(char* pDevId, bool bCaptureAudio, bool bTowWayCall);
FUNCLIB_LIBRARY int FC_StartTalk(char* pDevId);

/*
 函数名称：FC_StartTalkWithNVR
 函数功能：与NVR设备本身对讲(与NVR下的通道设备对讲时请使用接口FC_StartTalk)
 参数说明：pDevId：设备id
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_StartTalkWithNVR(char* pDevId);

/*
 函数名称：FC_InputAudioData
 函数功能：传入对讲数据,调用此函数的前提的FC_StartTalk对讲启动成功。
 参数说明：pDevId: 设备ID，TPS_AudioData：采集编码好的数据
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_InputAudioData(char*pDevId, TPS_AudioData oAudioData);

/*
 函数名称：FC_StopTalk
 函数功能：停止对讲
 参数说明：pDevId：设备id bTowWayCall：是否双向通话
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_StopTalk(char* pDevId, bool bTowWayCall);

FUNCLIB_LIBRARY int FC_SetSoundFile(const char *pDevId, const char *pSoundFile);

/*
 函数名称：FC_SetUploadFile
 函数功能：启动上传文件
 参数说明：pDevId: 设备ID，nFileType: 文件类型(0为配置文件，1 为固件，2为音频文件，3为用于产测上传配置文件包, 4 人脸特征YUV导入, 8：AI算法安装包文件)，pFile: 文件路径，szExtraParams: 附加参数
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_SetUploadFile(const char *pDevId, const int nFileType, const char *pFile, const char *szExtraParams);

/*
 函数名称：FC_StartUploadFile
 函数功能：创建上传文件的线程，如需上传音频文件调用此接口后再使用FC_SetSoundFile接口进行上传
 参数说明：pDevId: 设备ID
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_StartUploadFile(char *pDevId);

/*
 函数名称：FC_StopUploadFile
 函数功能：停止上传文件
 参数说明：pDevId: 设备ID
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_StopUploadFile(char *pDevId);

/*
 函数名称：FC_GetRegNumber
 函数功能：获取手机或者邮箱注册验证码
 参数说明：pPhoneMail：对应注册的手机号码或者注册的邮箱地址；pLang：注册验证语言，支持zh-cn, zh-tw, en-us
 返回值：0:函数调用成功；非0：函数调用失败，错误码如下：
 */
enum E_GET_VERIFY_CODE_ERROR{
    get_reg_number_error_null = 0,
    get_reg_number_error_param,//参数错误，比如手机号码不正确，邮箱不正确
    get_reg_number_error_quik,//一分钟内重复发送多次，发送间隔时间要大于1分钟
    get_reg_number_error_sendmsg,//发送手机短信失败，可能是手机号错误，或短信发送接口错误
    get_reg_number_error_phonemail_used,//手机或者邮箱已经被注册过
    get_reg_number_error_user_not_find,//用户账号不存在
    get_reg_number_error_user_phone,//用户账号和手机号码／邮箱地址不匹配
    get_reg_number_error_one_hour_limit,//1小时内发送的短信条数超过上限
    get_reg_number_error_one_day_limit,//当天发送的短信条数超过上限
    get_reg_number_error_content_same_limit,//发送相同内容的短信条数超过上限
    get_reg_number_error_phonenumber_in_blacklsit,//手机号在黑名单库中
    get_reg_number_error_request_timeout,//请求下发短信超时
    get_reg_number_error_user_not_login,//用户未登录
    get_reg_number_error_user_is_binded,//用户已经绑定过手机或邮箱
    get_reg_number_error_other,
};
FUNCLIB_LIBRARY int FC_GetRegNumber(char *pPhoneMail, char *pLang);

/*
 函数名称：FC_GetResetRegNumber
 函数功能：获取重置密码的验证码
 参数说明：pPhoneMail：对应注册的手机号码或者注册的邮箱地址；pUser:新账号对应pPhoneMail值,旧账号对应旧账号值;pLang：注册验证语言，支持zh-cn, zh-tw, en-us
 返回值：0:函数调用成功；非0：函数调用失败，错误码参考FC_GetRegNumber定义：
 */
FUNCLIB_LIBRARY int FC_GetResetRegNumber(char *pPhoneMail, char *pUser, char *pLang);

/*
 函数名称：FC_ResetUserPassword
 函数功能：重置用户密码
 参数说明：pPhoneMail：对应注册的手机号码或者注册的邮箱地址；pUser:新账号对应pPhoneMail值,旧账号对应旧账号值; pPassword:重置密码; pCode:验证码（FC_GetResetRegNumber获取）; pLang：注册验证语言，支持zh-cn, zh-tw, en-us
 返回值：0:函数调用成功；非0：函数调用失败，错误码参考定义：
 */
enum{
    reset_psw_error_null=0,
    reset_psw_error_user_empty,//用户账号为空
    reset_psw_error_code_valid,//验证码过期或未成功发送验证码
    reset_psw_error_code,//验证码错误
    reset_psw_error_user,//用户账号和手机号码／邮箱地址不匹配
};
FUNCLIB_LIBRARY int FC_ResetUserPassword(char *pPhoneMail, char *pUser, char *pPassword, char *pCode, char *pLang);

/*
 函数名称：FC_RegCSUserEx
 函数功能：云服务器用户注册
 参数说明：pUserName：用户名；pPassword：用户密码；pMail：邮箱（非必填）；pPhone（非必填）；pCode：验证码(FC_GetRegImg函数获取到的图片显示数字)
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下
 */
enum{
    reg_error_null = 0,
    reg_error_user,
    reg_error_password,
    reg_error_code,
    reg_error_user_length,
    reg_error_psw_length,
    reg_error_mail,
    reg_error_phone,
    reg_error_user_exist,
    reg_error_other,
};

FUNCLIB_LIBRARY int FC_RegCSUserEx(char *pUserName, char *pPassword, char *pMail, char *pPhone, char *pCode, char *pEventId);

/*
 函数名称：FC_GetBindNumber
 函数功能：获取手机或者邮箱绑定验证码
 参数说明：nType：详见 E_VERIFY_NUMBER_TYPE；pPhoneMail：对应注册的手机号码或者注册的邮箱地址；pLang：注册验证语言，支持zh-cn, zh-tw, en-us；isModify：1是修改绑定关系，0是新建绑定关系
 当nType为user_withdraw时，无视pPhoneMail，isModify参数
 返回值：0:函数调用成功；非0：函数调用失败，错误码详见E_GET_VERIFY_CODE_ERROR
 */
enum E_VERIFY_NUMBER_TYPE {
    user_bind_by_phone = 0, //手机号绑定
    user_bind_by_email,     //电子邮箱绑定
    user_withdraw,          //用户注销
};
FUNCLIB_LIBRARY int FC_GetVerifyNumber(int nType, char *pPhoneMail, char *pLang, int isModify);

/*
 函数名称：FC_BindUser
 函数功能：用户绑定手机或电子邮箱
 参数说明：nBindType：详见 E_VERIFY_NUMBER_TYPE；pPhoneMail：手机号码或者邮箱地址；pCode：验证码(FC_GetBindNumber函数获取到的验证码)；isModify：1是修改绑定关系，0是新建绑定关系
 返回值：0:函数调用成功；非0:函数调用失败，错误码详见E_GET_VERIFY_CODE_ERROR
 */
enum {
    bind_user_err_null = 0,
    bind_user_err_user_not_login,
    bind_user_err_username_empty,
    bind_user_err_code_empty,
    bind_user_err_code_error,
    bind_user_err_save_failed,
    bind_user_err_null_need_relogin,
    bind_user_err_other,
};
FUNCLIB_LIBRARY int FC_BindUser(int nBindType, char *pPhoneMail, char *pCode, int isModify);

/*
 函数名称：FC_CheckAccountRegByToken
 函数功能：一键注册前检查本机手机号是否已经注册
 参数说明：pToken：运营商token；nOperatorPlatform：接入平台,1->为创蓝闪验,2->腾讯号码验证；nPhonePlatform：客户端类型 1 为Android 2 为IOS；pAppName：天视通：seetong（默认） 莱诺威：usee 乔安：qiaoan
 返回值：0:成功；非0:失败，错误码如下：
 */
enum {
    check_account_reg_err_null = 0,
    check_account_reg_err_onekey_auth_fail,
    check_account_reg_err_database,
    check_account_reg_err_mobile_phone_be_registered,
    check_account_reg_err_other,
};
FUNCLIB_LIBRARY int FC_CheckAccountRegByToken(const char *pToken, int nOperatorPlatform, int nPhonePlatform, const char *pAppName);

/*
 函数名称：FC_RegisterAccountWithToken
 函数功能：用户本机号码一键注册
 参数说明：pToken：运营商token；nOperatorPlatform：接入平台,1->为创蓝闪验,2->腾讯号码验证；nPhonePlatform：客户端类型 1 为Android 2 为IOS；pPassword：用户设置的登录密码；
 返回值：0:成功；非0:失败，错误码如下：
 */
enum {
    register_with_token_err_null = 0,
    register_with_token_err_onekey_auth_fail,
    register_with_token_err_database,
    register_with_token_err_mobile_phone_be_registered,
    register_with_token_err_other,
};
FUNCLIB_LIBRARY int FC_RegisterAccountWithToken(const char *pToken, int nOperatorPlatform, int nPhonePlatform, const char *pPassword ,const char *pEventId);

/*
 函数名称：FC_BindMobileWithToken
 函数功能：用户绑定本机手机号
 参数说明：pToken：运营商token；nOperatorPlatform：接入平台,1->为创蓝闪验,2->腾讯号码验证；nPhonePlatform：客户端类型 1 为Android 2 为IOS；pAppName：天视通：seetong（默认） 莱诺威：usee 乔安：qiaoan
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下：
 */
enum {
    bind_mobile_phone_err_null = 0,
    bind_mobile_phone_err_onekey_auth_fail,
    bind_mobile_phone_err_database,
    bind_mobile_phone_err_mobile_phone_be_used,
    bind_mobile_phone_err_null_need_relogin, //绑定成功，但需要重新登录
    bind_mobile_phone_err_other,
};
FUNCLIB_LIBRARY int FC_BindMobileWithToken(const char *pToken, int nOperatorPlatform, int nPhonePlatform, const char *pAppName);

/*
 函数名称：FC_CheckAccountResetPassByToken
 函数功能：一键重置密码前检查本机手机号是否已经注册
 参数说明：pToken：运营商token；nOperatorPlatform：接入平台,1->为创蓝闪验,2->腾讯号码验证；nPhonePlatform：客户端类型 1 为Android 2 为IOS；pAppName：天视通：seetong（默认） 莱诺威：usee 乔安：qiaoan
 返回值：0:成功；非0:失败，错误码如下：
 */
enum {
    check_account_resetpass_err_null = 0,
    check_account_resetpass_err_onekey_auth_fail,
    check_account_resetpass_err_database,
    check_account_resetpass_err_not_find_user,
    check_account_resetpass_err_account_exception, //可发起申诉
    check_account_resetpass_err_other,
};
FUNCLIB_LIBRARY int FC_CheckAccountResetPassByToken(const char *pToken, int nOperatorPlatform, int nPhonePlatform, const char *pAppName);

/*
 函数名称：FC_ResetAccountPassWithToken
 函数功能：一键重置本机手机号用户密码
 参数说明：pToken：运营商token；nOperatorPlatform：接入平台,1->为创蓝闪验,2->腾讯号码验证；nPhonePlatform：客户端类型 1 为Android 2 为IOS；pPassword：用户设置的登录密码；
 返回值：0:成功；非0:失败，错误码如下：
 */
enum {
    reset_user_password_with_token_err_null = 0,
    reset_user_password_with_token_err_onekey_auth_fail,
    reset_user_password_with_token_err_database,
    reset_user_password_with_token_err_not_find_user,
    reset_user_password_with_token_err_account_exception, //可发起申诉
    reset_user_password_with_token_err_other,
};
FUNCLIB_LIBRARY int FC_ResetAccountPassWithToken(const char *pToken, int nOperatorPlatform, int nPhonePlatform, const char *pPassword);

/*
 函数名称：FC_WithdrawUserWithToken
 函数功能：用户通过本机号码验证身份操作账号注销
 参数说明：pToken：运营商token；nOperatorPlatform：接入平台,1->为创蓝闪验,2->腾讯号码验证；nPhonePlatform：客户端类型 1 为Android 2 为IOS；pAppName：天视通：seetong（默认） 莱诺威：usee 乔安：qiaoan
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下：
 */
enum {
    withdraw_user_with_token_err_null = 0,
    withdraw_user_with_token_err_onekey_auth_fail,
    withdraw_user_with_token_err_database,
    withdraw_user_with_token_err_unbind_the_mobile,
    withdraw_user_with_token_err_not_find_user,
    withdraw_user_with_token_err_exist_add_device,
    withdraw_user_with_token_err_other,
};
FUNCLIB_LIBRARY int FC_WithdrawUserWithToken(const char *pToken, int nOperatorPlatform, int nPhonePlatform, const char *pAppName);

/*
 函数名称：FC_WithdrawUser
 函数功能：用户注销
 参数说明：pCode：验证码(FC_GetVerifyNumber函数获取到的验证码)；
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下：
 */
enum {
    withdraw_user_err_null = 0,
    withdraw_user_err_user_not_login,
    withdraw_user_err_code_empty,
    withdraw_user_err_unbind,
    withdraw_user_err_db_err,
    withdraw_user_err_exist_added_device,
    withdraw_user_err_code_error,
    withdraw_user_err_user_not_find,
    withdraw_user_err_svr_err,
    withdraw_user_err_other,
};
FUNCLIB_LIBRARY int FC_WithdrawUser(char *pCode);

/*
 函数名称：FC_QuerySharingUserInfo
 函数功能：查询分享用户的信息
 参数说明：pDevId：设备ID
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下
 */
enum  {
    base_error_null = 0,
    base_error_param_null,
    base_error_notlogin,
    base_error_no_take_uid,
    base_error_database_fail,
    base_error_not_bind_dev,
    base_error_num_reached_full,
    base_error_share_code_null,
    base_error_share_code_expire,
    base_error_share_code_being_used,
    base_error_dev_exist,
    base_error_other,
};
FUNCLIB_LIBRARY int FC_QuerySharingUserInfo(char* pDevId);

/*
 函数名称：FC_DeleteSharingDevice
 函数功能：删除分享出去的对方列表设备
 参数说明：pDevId：设备ID  pUserId:用户id
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下
 */
FUNCLIB_LIBRARY int FC_DeleteSharingDevice(char* pDevId, char* pUserId);
    
/*
 函数名称：FC_GetDeviceSharingCode
 函数功能：获取已绑定设备的分享码
 参数说明：pDevId：设备ID  pVer:app版本号 pAuth:分享权限 pChannels:通道，当设备为NVR时必须上报此参数，多个以逗号分离，如1,2,3,4,5；对不支持通道的设备，参数不传值,NVR通道编号以数字1编号开始
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下
 */
FUNCLIB_LIBRARY int FC_GetDeviceSharingCode(char* pDevId, char* pVer, const char *pAuth, const char *pChannels);
  
/*
 函数名称：FC_AddDeviceBySharingCode
 函数功能：通过分享码添加设备
 参数说明：pDevId：设备ID  pCode:分享码
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下
 */
FUNCLIB_LIBRARY int FC_AddDeviceBySharingCode(char* pDevId, char* pCode);

/*
 函数名称：FC_ShareDevByPhoneEmail
 函数功能：通过手机号或邮箱分享设备
 参数说明：{"id": "1","v": "1","chs": "111","pers": "100,001","phoneOrEmail": "111@qq.com"}
 返回值：200:函数调用成功；其他:函数调用失败
 */
FUNCLIB_LIBRARY int FC_ShareDevByPhoneEmail(const char *jsonData);

/*
 函数名称：FC_GetShareAuthSetList
 函数功能：通过服务器查询可设置的分享权限项列表
 参数说明：pLanguage：APP语言 nDeviceType: 设备类型,默认101
 返回值：0:函数调用成功；非0:函数调用失败，查询结果回调消息TPS_MSG_NOTIFY_GET_SHARE_AUTH_SET_LIST
 */
FUNCLIB_LIBRARY int FC_GetShareAuthSetList(const char *pLanguage, const int nDeviceType);

/*
 函数名称：FC_GetSharingDeviceUserDetailInfo
 函数功能：从服务器获取分享给用户的权限详细信息
 参数说明：pDevId：设备ID pUserId:分享添加者用户ID pLanguage：APP语言
 返回值：0:函数调用成功；非0:函数调用失败，查询结果回调消息TPS_MSG_NOTIFY_GET_SHARING_DEVICE_USER_DETAIL_INFO,
 */
FUNCLIB_LIBRARY int FC_GetSharingDeviceUserDetailInfo(const char *pDevId, const char *pUserId, const char *pLanguage);

/*
 函数名称：FC_ModifySharingDeviceAuth
 函数功能：修改设备分享权限信息
 参数说明：pDevId：设备ID pUserId:分享添加者用户ID pAuth：分享权限 pChannels:通道，当设备为NVR时必须上报此参数，多个以逗号分离，如1,2,3,4,5；对不支持通道的设备，参数不传值,NVR通道编号以数字1编号开始
 返回值：0:函数调用成功；非0:函数调用失败，修改结果回调消息TPS_MSG_NOTIFY_MODIFY_SHARING_DEVICE_AUTH
 */
FUNCLIB_LIBRARY int FC_ModifySharingDeviceAuth(const char *pDevId, const char *pUserId, const char *pAuth, const char *pChannels);

/*
 函数名称：FC_QueryAllDevSharingInfo
 函数功能：获取用户的所有分享设备的权限
 参数说明：pDevId:参数可选 不带：返回所有分享设备的权限 带：返回该设备所有通道的权限
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下及server_request_error公共错误
 */
enum  {
    query_all_dev_shareinfo_error_null = 0,
    query_all_dev_shareinfo_error_database_fail,
};
FUNCLIB_LIBRARY int FC_QueryAllDevSharingInfo(const char *pDevId);

/*
 函数名称：FC_GetDeviceBindUsersList
 函数功能：查询添加设备的用户列表信息
 参数说明：pSerialNumber：设备序列号
 返回值：0:函数调用成功；非0:函数调用失败，查询结果回调消息TPS_MSG_NOTIFY_GET_DEVICE_BIND_USERS_LIST,
 */
enum {
    get_device_users_error_null = 0,
    get_device_users_error_notlogin,
    get_device_users_error_database_fail,
    get_device_users_error_device_not_exist,
    get_device_users_error_no_permission,
    get_device_users_error_not_support_query,
    get_device_users_error_other,
};
FUNCLIB_LIBRARY int FC_GetDeviceBindUsersList(const char *pSerialNumber);

/*
 函数名称：FC_TransferDevice
 函数功能：设备转移给其他用户
 参数说明：pDevId：设备ID pPhoneOrEmail:对方绑定的手机号/邮箱 nInstallBind:1勾选装机上报选项， 0不勾选， 默认值为false
 返回值：0:函数调用成功；非0:函数调用失败
 */
enum  {
    transfer_device_error_null = 0,
    transfer_device_error_notlogin,
    transfer_device_error_database_fail,
    transfer_device_phone_bind_abnormal,
    transfer_device_email_bind_abnormal,
    transfer_device_user_not_exist,
    transfer_device_can_not_onself,
    transfer_device_no_bind_device,
    transfer_device_value_addid_service_fail,
    transfer_device_error_other,
};
FUNCLIB_LIBRARY int FC_TransferDevice(const char *pDevId, const char *pPhoneOrEmail, int nInstallBind);

/*
 函数名称：FC_modifyUserPassword
 函数功能：为用户修改密码
 参数说明：pOldPwd：用户旧密码  pNewPwd用户新密码
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下
 */
enum  {
    mup_error_null = 0,
    mup_error_oldpwd_error,
    mup_error_param_null,
    mup_error_database_fail,
    mup_error_notlogin,
    mup_error_other,
    };
FUNCLIB_LIBRARY int FC_ModifyUserPassword(char *pOldPwd, char *pNewPwd);
    
/*
 函数名称：FC_AddDevice
 函数功能：为注册用户添加设备
 参数说明：pDevId：设备ID；pDevUser：设备账号；pDevPassword：设备密码  nBind_way：添加方式 0=>其他 （兼容之前的版本） 1=> 扫码 2=>局域网 3=> 手动输入用户名密码
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下
 注意：此函数必须是按用户账号登陆云服务器后才调用此函数为该用户添加设备
 */
enum  {
    ad_error_null = 0,
    ad_error_notlogin,
    ad_error_id,
    ad_error_dev_exist,
    ad_error_dev_lock,
    ad_error_user_psw,
    ad_error_dev_no_right,
    ad_error_other,
    ad_error_dev_id_not_exist,
    ad_error_password_too_simple,
    ad_error_be_bound,
    ad_error_not_support_the_bind_way,
    ad_error_today_use_error_psw_limit_add,
    ad_error_today_use_default_psw_limit_add,
    };

FUNCLIB_LIBRARY int FC_AddDevice(char* pDevId, char *pDevUser, char *pDevPassword, char *pDevAlias, int nBind_way);

/*
 函数名称：FC_DelDevice
 函数功能：删除用户账号下添加的设备
 参数说明：pDevId：设备ID
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下
 注意：此函数必须是按用户账号登陆云服务器后才调用此函数删除用户添加的设备
 */
enum  {
    del_error_null = 0,
    del_error_notlogin,
    del_error_id,
    del_error_connect_failed,
    del_error_user_disabled,
    del_error_user_no_auth,
    del_error_connect_micro_server_error,
    del_error_micro_server_error,
    del_error_other,
};

FUNCLIB_LIBRARY int FC_DelDevice(char* pDevId);

FUNCLIB_LIBRARY int FC_DelDeviceStream(char* pDevId);

FUNCLIB_LIBRARY int FC_GetDeviceNetworkQSInfo(char* pDevId);

/*
 函数名称：FC_ModifyDevName
 函数功能：修改设备备注名
 参数说明：pDevId：设备ID；pDevNewName：设备备注名称；nLoginByUser：登陆方式，按用户登陆填1，按设备ID登陆填0
 返回值：0:函数调用成功；非0:函数调用失败，错误码如下
 注意：设备的备注名如果是中文必须是utf-8编码
 */
enum  {
    md_error_null = 0,
    md_error_id_null,
    md_error_name_null,
    md_error_dev_notfind,
    md_error_user_psw,
    md_error_connect_failed,
    md_error_user_not_login,
    md_error_connect_db_error,
    md_error_connect_micro_server_error,
    md_error_micro_server_error,
    md_error_other,
};

FUNCLIB_LIBRARY int FC_ModifyDevName(char* pDevId, char *pDevNewName, int nLoginByUser);
/*
 函数名称：FC_ModifyDevPassword
 函数功能：更新修改后的设备密码
 参数说明：pDevId：设备ID; pDevName:修改后的设备账号; pDevPswd：修改后的设备密码
 返回值：0:函数调用成功。非0失败共用上面错误码
 注意：只有确认设备密码修改成功后才能调用此接口更新，否则会导致该设备无法登陆。
 */
FUNCLIB_LIBRARY int FC_ModifyDevPassword(char* pDevId, char *pDevUser, char *pDevPswd);

/*
 函数名称：FC_StopDevCom
 函数功能：停止与设备之间的通信
 参数说明：pDevId：设备ID;
 返回值：0:函数调用成功。非0失败
 */
FUNCLIB_LIBRARY int FC_StopDevCom(char *pDevId);

/*
 函数名称：FC_StopDevComEx
 函数功能：停止所有设备之间的通信
 参数说明：
 返回值：0:函数调用成功。非0失败
 */
FUNCLIB_LIBRARY int FC_StopDevComEx();

/*
 函数名称：FC_ResumeDevCom
 函数功能：唤醒设备通信
 参数说明：
 返回值：0:函数调用成功。非0失败
 */
FUNCLIB_LIBRARY int FC_ResumeDevCom();

/*
 函数名称：ResumeDevComWithId
 函数功能：唤醒设备通信
 参数说明：pDevId 设备云ID
 返回值：0:函数调用成功。非0失败
 */
FUNCLIB_LIBRARY int FC_ResumeDevComWithId(const char* pDevId);

/*
 函数名称：FC_GetP2PDevConfig
 函数功能：读取设备配置
 参数说明：pDevId：设备ID nCommand：配置对应信息，请参考文档; pXml:xml文本内容
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
FUNCLIB_LIBRARY int FC_GetP2PDevConfig(char* pDevId, int nCommand, char *pXml);

/*
 函数名称：FC_GetP2PDevConfigWithPte
 函数功能：读取设备配置
 参数说明：pDevId：设备ID nCommand：配置对应信息，请参考文档; pXml:xml文本内容 nTransChannel:nvr端ipc对应的通道值，通道值用来判断是否需要透传消息
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
FUNCLIB_LIBRARY int FC_GetP2PDevConfigWithPte(char* pDevId, int nCommand, char* pXml, int nTransChannel);
    
/*
 函数名称：FC_SetP2PDevConfig
 函数功能：设置设备配置
 参数说明：pDevId：设备ID; nCommand：配置对应信息，请参考文档; pXml:配置xml文本内容
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
FUNCLIB_LIBRARY int FC_SetP2PDevConfig(char* pDevId, int nCommand, char *pXml);

/*
 函数名称：FC_SetP2PDevConfigWithPte
 函数功能：读取设备配置
 参数说明：pDevId：设备ID nCommand：配置对应信息，请参考文档; pXml:xml文本内容 nTransChannel:nvr端ipc对应的通道值，通道值用来判断是否需要透传消息
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
FUNCLIB_LIBRARY int FC_SetP2PDevConfigWithPte(char* pDevId, int nCommand, char* pXml, int nTransChannel);

/*
 函数名称：FC_P2PDevSystemControl
 函数功能：对设备进行高级系统控制
 参数说明：pDevId：设备ID nCommand：配置对应信息，请参考文档; pXml:配置xml文本内容
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
FUNCLIB_LIBRARY int FC_P2PDevSystemControl(char* pDevId, int nCommand, char *pXml);

/*
 函数名称：FC_P2PDevSystemControlWithPte
 函数功能：对设备进行高级系统控制
 参数说明：pDevId：设备ID nCommand：配置对应信息，请参考文档; pXml:配置xml文本内容 nTransChannel为通道值 nTransChannel>-1表示此消息需要透传
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
FUNCLIB_LIBRARY int FC_P2PDevSystemControlWithPte(char* pDevId, int nCommand, char* pXml, int nTransChannel);
    
/*
 函数名称：FC_SetAutoRecvAlm
 函数功能：设置设备是否自动接收告警（不处于播放状态的时候也能接收告警）
 参数说明：pDevId：设备ID; nRecvAlm: 1表示不处于播放状态的时候也能自动接收告警，0：表示不处于播放状态的时候不自动接收告警
 返回值：0:函数调用成功
 */
FUNCLIB_LIBRARY int FC_SetAutoRecvAlm(char* pDevId, int nRecvAlm);

enum REPLAY_IPC_ACTION
{
    ACTION_PLAY=0,
    ACTION_PAUSE,
    ACTION_RESUME,
    ACTION_FAST,
    ACTION_SLOW,
    ACTION_SEEK,
    ACTION_FRAMESKIP,
    ACTION_STOP,
    ACTION_CAPIMG=10,
    ACTION_CHANGE_SOUND,
    ACTION_RECV_DECODEPARAM,
};

/*
 函数名称：FC_GetDevPicture
 函数功能：告警发生时客户端向摇头机获取抓拍的图片
 参数说明：pDevId：设备ID; nStreamNo:获取设备哪一路码流的图片,0:主码流，1:子码流; pSavePathFile:存储路径文件名称，jpg格式，如：/users/xx/1.jpg
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回
 */
FUNCLIB_LIBRARY int FC_GetDevPicture(char* pDevId, int nStreamNo, char *pSavePathFile);

/*
 函数名称：FC_GetDevNatType
 函数功能：获取设备的NATTYPE值
 参数说明：pDevId：设备ID;
 返回值：nattype <=0 获取失败； =16表示转发，>0&!=16表示P2P
 */
FUNCLIB_LIBRARY int FC_GetDevNatType(char *pDevId);

/*
 函数名称：FC_P2PSearchNvrRecByTime
 函数功能：查询nvr录像
 参数说明：pDevId：设备ID;pDate：查询日期，例如：“20151015”
 返回值：0：成功，！＝0：失败
 注意：查询结果通过消息通知返回，用1440个字符来表示，如：“ABCABC....”,'A':表示定时录像；‘B’:表示报警录像，‘C’:表示手动录像
 */
FUNCLIB_LIBRARY int FC_P2PSearchNvrRecByTime(char *pDevId, char* pDate);

/*
 函数名称：FC_P2PSearchNvrRecByTimeEx
 函数功能：查询nvr录像,查询结果回调TPS_MSG_RSP_SEARCH_NVR_REC_SEC,返回TPS_NVR_REC_TIMES_INFO结构体
 参数说明：pDevId：设备ID;pDate：查询日期，例如：“20151015”
 返回值：0：成功，！＝0：失败
 */
FUNCLIB_LIBRARY int FC_P2PSearchNvrRecByTimeEx(char *pDevId, char *pDate);

/*
 函数名称：FC_P2PNvrReplayByTime
 函数功能：按时间播放nvr录像
 参数说明：pDevId：设备ID;pDateTime：播放时间点，例如：“20151015114030”；lRecordType：录像类型，例如：“7”(普通录像+手动录像+报警录像) nAudioEnable:步请求音频流 1请求音频流
 返回值：0：成功，！＝0：失败
 注意：媒体数据通过回调函数返回
 */
enum NVR_RECORD_TYPE
{
    NVR_SCHEDULE_VIDEO      = 0x0001,   //普通录像
    NVR_MANUAL_VIDEO        = 0x0002,   //手动录像
    NVR_ALARM_VIDEO         = 0x0004,   //报警录像
    NVR_MOTION_VIDEO        = 0x0008,   //移动录像
    NVR_REGIONAL_VIDEO      = 0x0010,   //区域入侵
    NVR_CROSS_VIDEO         = 0x0020,   //越界侦测
    NVR_LICENSE_PLATE_VIDEO = 0x0040,   //车牌识别
    NVR_HUMAN_FACE_VIDEO    = 0x0080,   //人脸识别
    NVR_HUMAN_FORM_VIDEO    = 0x0100,   //人形识别
    NVR_VEHICLE_FORM_VIDEO  = 0x0200,   //车形识别
	NVR_ANIMAL_VIDEO		= 0x0400,   //动物识别
	NVR_TUMBLE_VIDEO		= 0x0800,	//跌倒识别
	NVR_HIGH_PARABOLA_VIDEO	= 0x1000,   //高空抛物
};
FUNCLIB_LIBRARY int FC_P2PNvrReplayByTime(char *pDevId, char* pDateTime, unsigned int lRecordType, int nAudioEnable);

/*
 函数名称：FC_ControlNVRReplay
 函数功能：nvr回放控制
 参数说明：pDevId：设备ID;lAction：控制命令，参考枚举值，lSpeed：速度；pPlayTime：seek控制命令时的播放时间点，例如：“201510151140”
 返回值：0：成功，！＝0：失败
 */
enum REPLAY_NVR_ACTION
{
    NVR_ACTION_RESUME=1,
    NVR_ACTION_PAUSE,
    NVR_ACTION_STOP,
    NVR_ACTION_FAST,
    NVR_ACTION_SLOW,
    NVR_ACTION_SEEK,
    NVR_ACTION_FRAMESKIP,
    NVR_ACTION_NORMAL,
};
FUNCLIB_LIBRARY int FC_ControlNVRReplay(char *pDevId, unsigned int lAction, unsigned int lSpeed, char *pPlayTime);

/*
 函数名称：FC_P2PSearchNvrRecByMonth
 函数功能：查询nvr录像，一个月的录像情况
 参数说明：pDevId：设备ID;pDate：查询日期，例如：“201709”
 返回值：0：成功，！＝0：失败
 注意：查询结果通过消息通知返回，用当月总天数(28,29等)个字符来表示，如：“201709:101010....”,'201709:':表示2017年9月的录像情况；‘1’:表示当天有录像，‘0’:表示当天无录像
 */
FUNCLIB_LIBRARY int FC_P2PSearchNvrRecByMonth(char *pDevId, char* pDate);

/*
 函数名称：FC_P2PNVRRecordDownload
 函数功能：开始下载NVR录像文件
 参数说明：pDevId:设备id
 返回值：0：成功，！＝0：失败
 */
FUNCLIB_LIBRARY int FC_P2PNVRRecordDownload(char *pDevId, char *pStartTime, char *pEndTime, char *pSaveFile);

/*
 函数名称：FC_P2PNVRRecordDownloadStop
 函数功能：停止下载NVR录像文件
 参数说明：pDevId:设备id
 返回值：0：成功，！＝0：失败
 */
FUNCLIB_LIBRARY int FC_P2PNVRRecordDownloadStop(char *pDevId);

/*
 函数名称：FC_SearchIpType
 函数功能：查询ip归属运营商
 参数说明：ip：ip地址;
 返回值：>0：成功 <0：失败; 返回ip归属运营商包含：电信(1)、长宽(2)、联通(3)、铁通(4)、移动(5)、教育网(6)、未知(16)
 */
FUNCLIB_LIBRARY int FC_SearchIpType(char* ip);


/*
 函数名称：FC_UploadFile
 函数功能：上传文件（日志）到服务器
 参数说明：pPathfile：文件路径();
 返回值：=0：成功, !=0：失败;
 */
enum  {
    uf_error_null = 0,
    uf_error_param,
    uf_error_open_file,
    uf_error_memory,
    uf_error_socket,
};
FUNCLIB_LIBRARY int FC_UploadFile(char* pPathfile,char *pFileName);

/*
 函数名称：FC_SetTryP2PTimeout
 函数功能：设置p2p打洞超时时间（s），不设置默认是6秒。
 参数说明：nTime：设置范围>0,<3600;
 返回值：=0：成功, !=0：失败;
 */
FUNCLIB_LIBRARY int FC_SetTryP2PTimeout(int nTime);

/*
 函数名称：FC_ForceSubStreamByRelay
 函数功能：走转发的时候是否强制播放子码流，默认是强制播放子码流
 参数说明：bForce：true 强制播放子码流；false 不强制播放子码流
 返回值：=0：成功, !=0：失败;
 */
FUNCLIB_LIBRARY int FC_ForceSubStreamByRelay(bool bForce);

/*
 函数名称：FC_GetUpdateFWInfo
 函数功能：获取设备固件更新信息
 参数说明：pDevId:[in]设备id；pDevIdentify:[in]设备固件版本唯一标识，通过调用FC_P2PDevSystemControl接口取得；
 返回值：=0：成功, !=0：失败;
 */
enum
{
    gf_error_null = 0,
    gf_error_invalid_param,//无效参数
    gf_error_param_format,//参数格式错误
    gf_error_search_data,//数据查询错误
    gf_error_network,//网络异常
    gf_error_other,//未知
};
FUNCLIB_LIBRARY int FC_GetUpdateFWInfo(char *pDevId, char *pDevIdentify, char* capability, char *devSn);

/*
 函数名称：FC_AddFeedback
 函数功能：添加反馈信息
 参数说明：info:[in]反馈信息内容；phone:[in]联系方式; app_var: app版本号
 返回值：=0：成功, !=0：失败;
 */
FUNCLIB_LIBRARY int FC_AddFeedback(const char *info, const char *phone, const char *app_ver);

/*
 函数名称：FC_GetSystemNotify
 函数功能：获取服务器侧的系统消息
 参数说明：pLanguage:[in]语言类型
 返回值：=0：成功, !=0：失败;
 */
 enum  {
    get_system_notify_user_not_login = -1805001,      //用户未登陆
};
FUNCLIB_LIBRARY int FC_GetSystemNotify(const char *pLanguage);

FUNCLIB_LIBRARY const char* FC_GetSdkVersion();

/*
 函数名称：FC_SetUserInfo
 函数功能：设置当前登录用户信息
 参数说明：uname:[in]用户名；pwd:[in]密码
 返回值：=0：成功, !=0：失败;
 */
FUNCLIB_LIBRARY int FC_SetUserInfo(const char *uname, const char *pwd);

/*
 函数名称：FC_ForceRequstIframe
 函数功能：向设备端发送强制请求I帧命令
 参数说明：pDevId:设备id
 返回值：未使用
 */
FUNCLIB_LIBRARY int FC_ForceRequstIframe(char *pDevId, int nChannelId);

/*
 函数名称：FC_ForceRequstIframeEx
 函数功能：向设备端发送强制请求I帧命令的扩展接口，追加当前是否为回放的参数
 参数说明：pDevId:设备id
 返回值：未使用
 */
FUNCLIB_LIBRARY int FC_ForceRequstIframeEx(char *pDevId, int nChannelId, int bIsPlayBack);

/*
 Function Name: FC_SetHttpsProtocol();
 Description: set communication protocol by https
 Parameters:
 Return: 0: success, !=0: failed
 */
FUNCLIB_LIBRARY int FC_SetHttpsProtocol();

/*
 Function Name: FC_SetLargeDevlist();
 Description: set large device list, it`s only use on Android platform, no limit on create CP2PStream object counts.
 Parameters:
 Return: 0: success, !=0: failed
 */
FUNCLIB_LIBRARY int FC_SetLargeDevlist();

/*
 函数名称：FC_RemoteDiagnose
 函数功能：设备远程调试命令
 参数说明：pDevId：设备ID,nCommand:消息Code,pXml xml文本内容,nChannel 通道(设备直接交互-1,NVR通道相应通道号)
 返回值：0:函数调用成功
 */
FUNCLIB_LIBRARY int FC_RemoteDiagnose(char* pDevId, int nCommand, char* pXml, int nChannel);

/*************************************************************************************************************************
 *                                   设备直连访问相关定义
 **************************************************************************************************************************/
#define MAX_ALARM_DATA              (128)
#define MAX_IP_NAME_LEN             (256)
#define MAX_IP_ADDRESS_LEN          (255)
#define MAC_ADDRESS_LEN             (256)
#define MAX_IPC_SERIALNUMBER        (32)
#define MAX_DEVICETYPE_LEN_NETSDK   (128)
#define MAX_SALESAREA_LEN_NETSDK    (32)

#ifndef ZOOM_IN
#define ZOOM_IN     (ZOOM_IN_VALUE)
#define ZOOM_OUT    (ZOOM_OUT_VALUE)
#endif

enum ERROR_CODE
{
    ERR_WSASETUP_FAIL = -100,
    ERR_SSI_INIT_FAIL,
    ERR_SLOG_INIT_FAIL,
    ERR_CREATE_TASK_FAIL,
    ERR_PARAM_INVALID,
    ERR_XML_FORMAT_FAIL,
    ERR_PTZ_CMD_INVALID,
    ERR_UPLOAD_FILE_ERROR,
    ERR_UPLOAD_FILE_REFUSE,
    ERR_DOWNLOAD_FILE_REFUSE,
    ERR_SERIAL_NOT_START,
    ERR_NOT_ALLOW_REPLAY,
    ERR_DEV_NOT_CONNECTED,
    ERR_DEV_NOT_LOGIN,
    ERR_NOT_REPLAY_MODE,
    ERR_PLAY_ACTION,
    ERR_AUDIO_STARTED,
    
    ERR_NOT_FIND_DEVICE = -9000002,
    ERR_OPEN_AUDIOCAPTURE_FAIL,
    ERR_START_AUDIOCAPTURE_FAIL,
    ERR_AUDIO_PARAM_ERROR,
    ERR_MSGTYPE_ERROR,
    ERR_INIT_SOCKET_ERROR,
    ERR_PARAM_ERROR,
    ERR_NOT_DEV_EXIST,
    ERR_START_THREADERROR,
    ERR_NOT_FIND_STREAM,
    ERR_ISUPLOADING_ERROR,
    ERR_ISDOWNLOADING_ERROR,
    ERR_IS_STARTAUDIO_ERROR,
    ERR_ISFINISH_ERROR,
    ERR_NOT_DOWNLOAD_MODE_ERROR,
    ERR_PTZCMD_ACTION_ERROR,
    ERR_LOC_FILE_ERROR,
    ERR_NOT_REPLAY_MODE_ERROR,
    ERR_PLAY_ACTION_ERROR,
    ERR_NOT_ALLOW_REPLAY_ERROR,
    ERR_MEMORY_SIZE_ERROR,
    ERR_XML_FORMAT_ERROR,
    ERR_CREATE_SOCKET_ERROR,
    ERR_SEND_MODIFYCMD_ERROR,
    ERR_NOT_STARTTALK_MODE_ERROR,
    ERR_RECORD_MEDIA_PARAM_ERROR,
    ERR_RECORD_CREATEERROR,
    ERR_RECORD_ISRECORDING,
    ERR_RECORD_FILEMAXSECONDS_ERROR,
    ERR_RECORD_ALLRECORDSECONDS_ERROR,
    ERR_RECORD_NOTRUNNING,
    ERR_RECORD_STREAMPARAM_ERROR,
    ERR_RECORD_WRITETEMPBUFFER_ERROR,
    ERR_RECORD_ISNOTRECORDSTREAM_MODE,
    ERR_RECORD_NOTINPUTSTREAM_MODE,
    ERR_RECORD_FILEPATH_ERROR,
    ERR_DLL_NOINITORRELEASE_ERROR,
    ERR_NOT_FIND_FILEHANDLE,
    ERR_NOT_READMODE,
    ERR_OPEN_FILEERROR,
    ERR_MP4FILE_FORMAT_ERROR,
    ERR_READ_P2PNETWORK_ERROR,
};

enum enumNetSatateEvent
{
    EVENT_CONNECTING,
    EVENT_CONNECTOK,
    EVENT_CONNECTFAILED,
    EVENT_SOCKETERROR,
    EVENT_LOGINOK,
    EVENT_LOGINFAILED,
    EVENT_STARTAUDIOOK,
    EVENT_STARTAUDIOFAILED,
    EVENT_STOPAUDIOOK,
    EVENT_STOPAUDIOFAILED,
    EVENT_SENDPTZOK,
    EVENT_SENDPTZFAILED,
    EVENT_SENDAUXOK,
    EVENT_SENDAUXFAILED,
    EVENT_UPLOADOK,
    EVENT_UPLOADFAILED,
    EVENT_DOWNLOADOK,
    EVENT_DOWNLOADFAILED,
    EVENT_REMOVEOK,
    EVENT_REMOVEFAILED,
    EVENT_SENDPTZERROR,
    EVENT_PTZPRESETINFO,
    EVNET_PTZNOPRESETINFO,
    EVENT_PTZALARM,
    EVENT_RECVVIDEOPARAM,
    EVENT_RECVAUDIOPARAM,
    EVENT_CONNECTRTSPERROR,
    EVENT_CONNECTRTSPOK,
    EVENT_RTSPTHREADEXIT,
    EVENT_URLERROR,
    EVENT_RECVVIDEOAUDIOPARAM,
    EVENT_LOGIN_USERERROR,
    EVENT_LOGOUT_FINISH,
    EVENT_LOGIN_RECONNECT,
    EVENT_LOGIN_HEARTBEAT_LOST,
    EVENT_STARTAUDIO_ISBUSY,
    EVENT_STARTAUDIO_PARAMERROR,
    EVENT_STARTAUDIO_AUDIODDISABLED,
    EVENT_CONNECT_RTSPSERVER_ERROR,
    EVENT_CREATE_RTSPCLIENT_ERROR,
    EVENT_GET_RTSP_CMDOPTION_ERROR,
    EVENT_RTSP_AUTHERROR,
    EVNET_RECORD_FILEBEGIN,
    EVENT_RECORD_FILEEND,
    EVENT_RECORD_TASKEND,
    EVENT_RECORD_DISKFREESPACE_TOOLOW,
    EVNET_RECORD_FILEBEGIN_ERROR,
    EVNET_RECORD_WRITE_FILE_ERROR,
    EVENT_RECORD_INITAVIHEAD_ERROR,
    EVENT_RECORD_MEDIA_PARAM_ERROR,
    EVENT_NVR_CHANNELS,
    EVENT_NVR_IPC_STATUS,
    EVENT_NVR_RECORD_DOWNLOAD_START,
    EVENT_NVR_RECORD_DOWNLOAD_FAILED,
    EVENT_NVR_RECORD_DOWNLOAD_STOP,
    EVENT_NVR_RECORD_DOWNLOAD_PROGRESS,
    EVENT_SYSTEMREBOOT_ANDRELOGINOK,
    EVENT_NETWORKRESET_ANDRELOGINOK,
    EVENT_UPLOAD_PROCESS,
    EVENT_DOWNLOAD_PROCESS,
    EVENT_DOWNLOAD_RETRY_ANDRESTAR,
    EVENT_LOGOUT_BYUSER,
    EVENT_P2P_CONNECT_STATE_INFO,
    EVNET_INITP2P_OK,
    EVNET_INITP2P_ERROR,
    EVENT_START_CONNECT_DEVICE,
    EVENT_START_CONNECT_DEVICE_ERROR,
    EVENT_P2PSERVER_LOGIN_OK,
    EVENT_P2PSERVER_LOGOUT,
    EVENT_P2PERROR_EVNETINFO,
    EVENT_P2PCONNECT_DEVICEOK,
    EVENT_P2PCONNECT_CLOSE,
    EVENT_P2P_EXIT_CONNECT,
    EVENT_CAPTURE_IMAGE_FINISH,
    EVENT_RECVABLITY_INFO,
    EVENT_P2P_CLINET_CHANNLEINFO,
    EVENT_P2P_STARTSTREAM_ERROR11,
    EVENT_P2P_STOPSTREAM_ERROR,
    EVENT_RECV_BAD_TPSMSG_ERROR,
    EVENT_BURN_ALGORITHM,
    EVENT_NVR_RECORD_DOWNLOAD_FINISH,
};

enum ALGORITHM_ALARM_CODE
{
    ALARM_CODE_ALGORITHM_UPDATE_SUCCESS=48,             /*算法下载更新成功*/
    ALARM_CODE_ALGORITHM_UPDATE_FAIL=49,                /*算法下载更新失败*/
    ALARM_CODE_ALGORITHM_UNLOAD_SUCCESS=50,             /*算法卸载成功*/
    ALARM_CODE_ALGORITHM_UNLOAD_FAIL=51,                /*算法卸载失败*/
};

enum PTZ_PRESET_TYPE
{
    SET_PRESET = 8 , //设置
    CLE_PRESET = 9, //删除
    GOTO_PRESET = 39 //查询
};

enum SEARCH_EVENT
{
    EVENT_SEARCH_RECV_NEWIPCINFO = 1,//搜索设备时，找到新的设备
    EVENT_SEARCH_UPDATEINFO,//修改设备地址时，设备信息变化了
};

enum FILE_TYPE
{
    LOG_FILE,
    RECORD_FILE,
    CONFIG_FILE,
    UPDATE_FILE
};

typedef struct
{
    char  MACAddress[MAC_ADDRESS_LEN];
    int   dhcpEnable;
    char  IPAddress[MAX_IP_NAME_LEN];
    char  netMask[MAX_IP_NAME_LEN];
    char  gateWay[MAX_IP_NAME_LEN];
    char  DNS1[MAX_IP_NAME_LEN];
    char  DNS2[MAX_IP_NAME_LEN];
    int  nSetFlag;//==255 enable  bHaveAllNetConnectEnable
    int  bHaveAllNetConnectEnable;
}NetSDK_LANConfig;

typedef struct
{
    int   DevType;
    char  DeviceModule[MAX_IP_NAME_LEN];
    int   BindStatus;
    int   BindNetType;
    int   RegStatus;
}NetSDK_IOTInfo;
    
typedef struct
{
    int auth;
    int videoPort;
    int rtpoverrtsp;
    int ptzPort;
    int webPort;
}NetSDK_StreamAccessConfig;

#define GROUP_NAME_MAX_LEN          (32)
#define ACCOUNT_STATUS_MAX_LEN      (8)
#define ACCOUNT_NAME_MAX_LEN        (40)
#define ACCOUNT_PASSWORD_MAX_LEN    (40)
#define MAX_ACCOUNT_COUNT           (20)
typedef struct
{
    char    userName[ACCOUNT_NAME_MAX_LEN];
    char    password[ACCOUNT_PASSWORD_MAX_LEN];
    char    group[GROUP_NAME_MAX_LEN];
    char    status[ACCOUNT_STATUS_MAX_LEN];
}NetSDK_UserAccount;

typedef struct
{
    int count;
    NetSDK_UserAccount accounts[MAX_ACCOUNT_COUNT];
}NetSDK_UserConfig;

typedef struct
{
    char                        ipc_sn[MAX_IPC_SERIALNUMBER];
    char                        deviceType[MAX_DEVICETYPE_LEN_NETSDK];
    NetSDK_UserConfig           userCfg;
    NetSDK_StreamAccessConfig   streamCfg;
    NetSDK_LANConfig            lanCfg;
}NetSDK_IPC_ENTRY;

typedef struct __NetSDK_IPC_ENTRYV2
{
    char                        ipc_sn[MAX_IPC_SERIALNUMBER];
    char                        deviceType[MAX_DEVICETYPE_LEN_NETSDK];
	char						SalesArea[MAX_SALESAREA_LEN_NETSDK];
    int                         bindmode;
    NetSDK_UserConfig           userCfg;
    NetSDK_StreamAccessConfig   streamCfg;
    NetSDK_LANConfig            lanCfg;
    NetSDK_IOTInfo              iotInfo;
    //前面的为旧版本相关信息
    int                 nFlag;//调用读取时，要使用后面的数据，必须检查此标记是否为0x01020304,否则读取不到后面的扩展数据
    int                 nVersion;//调用读取时，版本号必须为1001,否则读不到云ID
    char                szCloudID[32];//云ID
    char                szOSD[256];
    char                szVerInfo[64];
    //
    int                 nDevSubType; //设备子类型0(默认，未区分类型)、1(有线+Wifi设备)、2(Wifi设备)、3(4G设备)，4(有线设备) 6(双内置卡4G)
    unsigned long long  ullFeature;  //64位的16进制数据类型，每个bit位表示一种功能属性，支持最多64种功能属性的叠加，比如枪球功能属性为0x1,低功耗属性为0x2,则fature字段为0x3,表示设备同时支持枪球和低功耗属性。
    // 通过哪个ip发送广播，而被搜索出来的
    char m_searchedLocalIP[MAX_IP_STRING_LEN];
}NetSDK_IPC_ENTRYV2;

typedef struct _FRAMNE_INFO
{
    int bIsVideo;
    int bIsKeyFrame;
    double TimeStamp;
}FRAMNE_INFO;

typedef struct
{
    int year;
    int month;
    int day;
    int wday;
    int hour;
    int minute;
    int second;
}NetSDK_ALARM_TIME;

typedef struct
{
    NetSDK_ALARM_TIME time;
    int code;
    int flag;
    int level;
    char data[MAX_ALARM_DATA];
}NetSDK_ALARM_ITEM;

typedef struct
{
    int    lChannel;
    int    lLinkMode;
    int    hPlayWnd;
    char    *sMultiCastIP;
}*LPIP_NET_DVR_CLIENTINFO, IP_NET_DVR_CLIENTINFO;

#define SERIALNO_LEN (48)
typedef struct
{
    unsigned char     sSerialNumber[SERIALNO_LEN];
    unsigned char     byAlarmInPortNum;
    unsigned char     byAlarmOutPortNum;
    unsigned char     byDiskNum;
    unsigned char     byDVRType;
    unsigned char     byChanNum;
    unsigned char     byStartChan;
}*LPIP_NET_DVR_DEVICEINFO, IP_NET_DVR_DEVICEINFO;

typedef struct
{
    
}IP_NET_DVR_ALARMER;

#define MAX_IPADDR_LEN (64)
typedef struct __USRE_VIDEOINFO
{
#if ((!defined(SDK_IOS)) && (!defined(SDK_ANDROID)) && (!defined(SDK_OHOS)))
    __USRE_VIDEOINFO(void):nVideoPort(-1),
        bIsTcp(0),nVideoChannle(0),
        pUserData(0),nVideoChannelIdx(-1){}
    ~__USRE_VIDEOINFO(void) {}
#endif
    //
    int  nVideoPort;
    int  bIsTcp;
    int  nVideoChannle;
    void *pUserData;
    // 播放的通道索引，-1，表示原有逻辑，否则表示拉第几个通道的视频
    int nVideoChannelIdx;
}USRE_VIDEOINFO, *LPUSRE_VIDEOINFO;

typedef struct __STREAM_AV_PARAM
{
    unsigned char   ProtocolName[32];
    short  bHaveVideo;
    short  bHaveAudio;
    NetSDK_VIDEO_PARAM videoParam;
    NetSDK_AUDIO_PARAM audioParam;
    char  szUrlInfo[512];
}NetSDK_STREAM_AV_PARAM;

typedef struct __StateEventMsgInfo
{
    char szInfo[1024];
    char szUrlInfo[512];
}STATE_EVENT_MSGINFO;

typedef struct
{
    int     bIsKey;
    double  timestamp;
    void    *pUserData;
    int     nFlag;//==FRAME_V2_FLAG_VALUE 标识符，用于兼容旧版本标识
    int     nChannel;//流通道
}FRAME_EXTDATA,* LPFRAME_EXTDATA;

#define FRAME_V2_FLAG_VALUE	(0x12340001)
#define AVI_RECORD_RESERVED_FREE_SPACE (2048)

typedef struct
{
    int                 stream_id;
    NetSDK_VIDEO_PARAM* video_param;
}NetSDK_VIDEO_STATE_MSG_PARAM;

typedef struct{
    unsigned int    dwSize;
    unsigned int    byDecChanScaleStatus;
}NET_DVR_MATRIX_DECCHAN_CONTROL;

typedef struct{
    char            sDVRIP[16];
    unsigned int    wDVRPort;
    unsigned int    wPTZPort;
    unsigned int    byChannel;
    unsigned int    byTransProtocol;
    unsigned int    byTransMode;
    char            sUserName[32];
    char            sPassword[32];
}NET_DVR_MATRIX_DECINFO;

typedef struct{
    unsigned int                    dwSize;
    NET_DVR_MATRIX_DECINFO   struDecChanInfo;
}NET_DVR_MATRIX_DYNAMIC_DEC;

#define MAX_VIDEO_CHAN (16)
typedef struct{
    unsigned int                    dwEnable;
    unsigned int                    dwVideoNum;
    NET_DVR_MATRIX_DECINFO   struDecChanInfo[MAX_VIDEO_CHAN];
}NET_DVR_MATRIX_DECCHANINFO;

#define MAX_CYCLE_CHAN (16)
typedef struct{
    unsigned int                    dwSize;
    unsigned int                    dwPoolTime;
    unsigned int                    dwPoolNum;
    NET_DVR_MATRIX_DECCHANINFO   struchanConInfo[MAX_CYCLE_CHAN];
}NET_DVR_MATRIX_LOOP_DECINFO;

typedef long(*SearchIPCCallBack)(long nEventCode, long index, NetSDK_IPC_ENTRY* pResponse, void* pUser);
typedef long(*MSGCallBack)(long lCommand, IP_NET_DVR_ALARMER* pAlarmer, char* pAlarmInfo, unsigned long BufLen, void* pUser);
typedef long(*StatusEventCallBack)(LONG_EX lUser, long nStateCode, char* pResponse, void* pUser);
typedef long(*AUXResponseCallBack)(LONG_EX lUser, long nType, char* pResponse, void* pUser);
typedef long(*fVoiceDataCallBack)(LONG_EX lVoiceComHandle, char* pRecvDataBuffer, unsigned long dwBufSize, unsigned char byAudioFlag, LPFRAME_EXTDATA pUser);
typedef long(*fRealDataCallBack)(LONG_EX lRealHandle, unsigned long dwDataType, unsigned char* pBuffer, unsigned long dwBufSize, LPFRAME_EXTDATA pExtData);
typedef long(*fPlayActionEventCallBack)(LONG_EX lUser, long nType, long nFlag, char* pData, void* pUser);
typedef long(*fExceptionCallBack)(unsigned long dwType, long lUserID, long lHandle, void* pUser);
typedef long(*fEncodeAudioCallBack)(long lType, long lPara1, long lPara2);
typedef long(*SerialDataCallBack)(LONG_EX lUser, char* pRecvDataBuffer, unsigned long dwBufSize, void* pUser);
typedef long(*fRecFileNameCallBack)(LONG_EX lRealHandle, char* pRecFileNameBuf, unsigned long dwBufSize, void* pUser);
typedef void(*fSDKLogCallBack)(const char* msg);
typedef long(*SearchIotBindStateCallBack)(int bindState, int bindflag, const char *serialNumber, const char *errorInfo);


int FC_MyDecrypt(char* pkey, char* pDat);
//search and modify IPC
FUNCLIB_LIBRARY int FC_Loc_SetAutoReconnect(int nReconnect);
FUNCLIB_LIBRARY int FC_Loc_SetSingleFixedIPTestMode(int nMode);
FUNCLIB_LIBRARY int FC_Loc_SetSearchStatusCallBack(SearchIPCCallBack fcallBack,void * pUser);
FUNCLIB_LIBRARY int FC_Loc_SetClearPreResultsBeforeSearch(bool isClear);
FUNCLIB_LIBRARY int FC_Loc_StartSearchIPC();
FUNCLIB_LIBRARY int FC_Loc_StartSearchIPCEX(char * strLocalIP, char *netInterfaceName);//指定网卡进行搜索设备，不需要可以传NULL
FUNCLIB_LIBRARY int FC_Loc_StopSearchIPC();
FUNCLIB_LIBRARY int FC_Loc_GetSearchIPCCount();
FUNCLIB_LIBRARY int FC_Loc_StartSearchIotIPC();//APP一键添加开始搜索IOT设备
FUNCLIB_LIBRARY int FC_Loc_StopSearchIotIPC();//APP一键添加停止搜索IOT设备
FUNCLIB_LIBRARY int FC_Loc_GetIPCInfo(long index, NetSDK_IPC_ENTRYV2 * pIPCInfo);
FUNCLIB_LIBRARY int FC_Loc_ModifyIPC(long index, NetSDK_IPC_ENTRYV2 * pIPCInfo, char *szNetworkCardIP);
FUNCLIB_LIBRARY int FC_Loc_ModifyIPCEx(long index, NetSDK_IPC_ENTRYV2 * pIPCInfo, bool bTempIp);
FUNCLIB_LIBRARY int FC_Loc_GetIPCInfoXML(long index, char * pXMLInfo,int maxLen);
FUNCLIB_LIBRARY int FC_Loc_ModifyIPCXML(long index, const char * strXML);
FUNCLIB_LIBRARY int FC_Loc_GetOneIPAddress(char * strResult,int nSize);
FUNCLIB_LIBRARY int FC_Loc_GetNetworkParam(long nParamIndex, char * strResult,int nSize);
FUNCLIB_LIBRARY int FC_Loc_RestoreIPC(long index, NetSDK_IPC_ENTRYV2 * pIPCInfo);
FUNCLIB_LIBRARY int FC_Loc_EnterProductionTestMode();
FUNCLIB_LIBRARY int FC_Loc_EnterProductionTestModeEx(long mode, char *pXml); //mode 0:工厂模式， 1：客户模式
FUNCLIB_LIBRARY int FC_Loc_ClearPreviousSearchResults(void);
//login IPC
FUNCLIB_LIBRARY int FC_Loc_SetStatusEventCallBack(StatusEventCallBack fStatusEventCallBack,void * pUser);

FUNCLIB_LIBRARY LONG_EX FC_Loc_LoginDev(char *sDVRIP,unsigned long wDVRPort,char *sUserName,char *sPassword,LPIP_NET_DVR_DEVICEINFO lpDeviceInfo, const char *netInfaceName, int nIPCChannel);
FUNCLIB_LIBRARY int FC_Loc_LogoutDev(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_UpdateDevLoginPwd(LONG_EX loginId, char* pUserName, char* pPassword);//修改设备登录用户与密码
//PTZ
FUNCLIB_LIBRARY int FC_Loc_PTZControlEx(LONG_EX lDevItem,char *pXml);
FUNCLIB_LIBRARY int FC_Loc_PTZPreset(LONG_EX lDevItem,unsigned long dwPTZPresetCmd,unsigned long dwPresetIndex);
FUNCLIB_LIBRARY int FC_Loc_PTZControl(LONG_EX lDevItem,unsigned long dwPTZCommand,unsigned long nTspeed,unsigned long nSpeed);
FUNCLIB_LIBRARY int FC_Loc_SetDVRMessageCallBack(MSGCallBack fMessageCallBack,void *pUser);
//config
FUNCLIB_LIBRARY int FC_Loc_GetDVRConfig(LONG_EX lDevItem,unsigned long dwCommand,long lChannel,void* lpOutBuffer,unsigned long dwOutBufferSize,unsigned long* lpBytesReturned, int nIPCChannel);
FUNCLIB_LIBRARY int FC_Loc_SetDVRConfig(LONG_EX lDevItem,unsigned long dwCommand,long lChannel,void* pXml,unsigned long dwInBufferSize, int nIPCChannel);//用于Msg_type=SYSTEM_CONFIG_SET_MESSAGE
FUNCLIB_LIBRARY int FC_Loc_SystemControl(LONG_EX lDevItem,unsigned long nCmdValue,long flag,char * pXml, int nIPCChannel);//用于Msg_type=SYSTEM_CONTROL_MESSAGE
FUNCLIB_LIBRARY int FC_Loc_SystemHWConfig(LONG_EX lDevItem,unsigned long nCmdValue,long flag,char * pXml);
FUNCLIB_LIBRARY int FC_Loc_WriteAUXStringEx(LONG_EX lDevItem,char * pMsgType,long nCode,long flag,char * pXml);
FUNCLIB_LIBRARY int FC_Loc_GetUserData(LONG_EX lDevItem,char * pOutBuffer,int* nInOutLen);
FUNCLIB_LIBRARY int FC_Loc_SetUserData(LONG_EX lDevItem,char * pBuffer,int len);
FUNCLIB_LIBRARY int FC_Loc_CreateIFrame(LONG_EX lDevItem,int bIsSubStream);
FUNCLIB_LIBRARY int FC_Loc_CreateIFrameEx(LONG_EX lDevItem,int bIsSubStream,int nChannelId, int nDirection);
FUNCLIB_LIBRARY int FC_Loc_RestoreConfig(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_RebootDVR(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_ShutDownDVR(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_GetDeviceAbility(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_FormatDisk(LONG_EX lDevItem, long lDiskNumber);
FUNCLIB_LIBRARY int FC_Loc_Upgrade(LONG_EX lDevItem, char *sFileName);
FUNCLIB_LIBRARY int FC_Loc_GetUpgradeProgress(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_GetUpgradeState(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_CloseUpgradeHandle(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_GetFileByName(LONG_EX lDevItem,long nFileType,char *sDVRFileName,char *saveDir);
FUNCLIB_LIBRARY int FC_Loc_StopGetFile(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_GetDownloadState(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_GetDownloadPos(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_SerialStart(LONG_EX lDevItem, SerialDataCallBack cbSDCallBack, void* pUser);
FUNCLIB_LIBRARY int FC_Loc_SerialSend(LONG_EX lDevItem, long lChannel, char *pSendBuf);
FUNCLIB_LIBRARY int FC_Loc_SerialStop(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_PostSerialMsg(void* obj, void* pAlarm);
FUNCLIB_LIBRARY int FC_Loc_MatrixStartDynamic(LONG_EX lDevItem, unsigned long dwDecChanNum, unsigned long dwVideoNum, NET_DVR_MATRIX_DYNAMIC_DEC lpDynamicInfo[MAX_VIDEO_CHAN]);
FUNCLIB_LIBRARY int FC_Loc_MatrixStopDynamic(LONG_EX lDevItem,  unsigned long dwDecChanNum);
FUNCLIB_LIBRARY int FC_Loc_MatrixSetLoopDecChanInfo(LONG_EX lDevItem, unsigned long dwDecChanNum, NET_DVR_MATRIX_LOOP_DECINFO lpInter);
FUNCLIB_LIBRARY int FC_Loc_GetConfigFile(LONG_EX lDevItem,char *sFileName);
FUNCLIB_LIBRARY int FC_Loc_SetConfigFile(LONG_EX lDevItem,char *sFileName);
FUNCLIB_LIBRARY int FC_Loc_SetAudioFile(LONG_EX lDevItem,char *sFileName);
FUNCLIB_LIBRARY int FC_Loc_SetCompressFile(LONG_EX lDevItem,char *sFileName);
FUNCLIB_LIBRARY int FC_Loc_SetLogoFile(LONG_EX lDevItem,char *sFileName);
FUNCLIB_LIBRARY int FC_Loc_SetAlgorithmFile(LONG_EX lDevItem,char *sFileName); //上传AI算法文件，参数 lDevItem：设备登录ID（唯一）
FUNCLIB_LIBRARY int FC_Loc_SetCompressFileEx(LONG_EX lDevItem,char *sFileName, int nLockParam);
FUNCLIB_LIBRARY int FC_Loc_FindDVRLogFile(LONG_EX lDevItem);
FUNCLIB_LIBRARY int FC_Loc_SystemTimeSync(LONG_EX lDevItem, long lEnable, long lMax_diff, long lInterval);
/* 设置并开始向设备上传文件
 * lDevItem：设备的连接句柄，由FC_Loc_LoginDev返回
 * nFileType：文件的类型，参考UPLOAD_FILE_TYPE定义
 * sFileName：文件名称（包括了路径）
*/
FUNCLIB_LIBRARY int FC_Loc_SetUploadFile(LONG_EX lDevItem,UPLOAD_FILE_TYPE nFileType,const char *sFileName);
//stream
FUNCLIB_LIBRARY LONG_EX FC_Loc_RealPlay(LONG_EX lDevItem,fRealDataCallBack cbRealDataCallBack,LPUSRE_VIDEOINFO pUser);
FUNCLIB_LIBRARY LONG_EX FC_Loc_RealPlayEx(LONG_EX lDevItem,char * serverip,char *user,char *pass,fRealDataCallBack cbRealDataCallBack,LPUSRE_VIDEOINFO pUser, const char *netInfaceName);
FUNCLIB_LIBRARY int FC_Loc_StopRealPlay(LONG_EX lRealHandle);
FUNCLIB_LIBRARY int FC_Loc_StopAllRealPlay();
FUNCLIB_LIBRARY int FC_Loc_GetVideoParam(LONG_EX  lRealHandle, NetSDK_VIDEO_PARAM *pParam);
FUNCLIB_LIBRARY int FC_Loc_GetAudioParam(LONG_EX lRealHandle, NetSDK_AUDIO_PARAM *pParam);
FUNCLIB_LIBRARY int FC_Loc_SetRealDataCallBack(fRealDataCallBack cbRealDataCallBack,void * dwUser);
//record
/*
 函数名称：
        FC_Loc_SetRecFileNameCallBack
 函数功能：
        如果需要自定制录制文件名，则使用此函数设置回调。
        设置后，创建文件之前则会进行回调，让用户进行自定义文件名。
 参数说明：
        lRealHandle:要录制的标识句柄，可以是FC_Loc_StartRecordStream返回的句柄
                    也可以是FC_Loc_RealPlayEx，FC_Loc_RealPlay调用时的返回句柄
        cbRecFileNameCallBack:[in]调用FC_Loc_StartRecordStream时的标识句柄
        pUser：[in]回调函数返回给用户的指针
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_SetRecFileNameCallBack(LONG_EX lRealHandle
                                  , fRecFileNameCallBack cbRecFileNameCallBack
                                  , void *pUser);

    
/*
 函数名称：FC_Loc_PlayBackStartRecord
 函数功能：局域网远程回放录像
 参数说明：
 lRealHandle:实例对象句柄
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_PlayBackStartRecord(LONG_EX lRealHandle, const char *pFile);
    
    
/*
 函数名称：FC_Loc_StopBackStartRecord
 函数功能：局域网远程回放停止录像
 参数说明：
 lRealHandle:实例对象句柄
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_StopBackStartRecord(LONG_EX lRealHandle);
/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_StartRecord(LONG_EX lRealHandle,const char * filePath,int nFileMaxSeconds,int nAllRecordMaxSeconds);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_StopRecord(LONG_EX lRealHandle);

/*
 函数名称：FC_Loc_StartRecordStreamEx
 函数功能：创建一个写MP4的文件，用于写数据
 参数说明：
            pAvParam:[in]编码参数
            filePath:[in]存储文件名
     nFileMaxSeconds:[in]输入参数 音频格式，支持AAC和G711
nAllRecordMaxSeconds:[in]最大录制时长
             bIsSub:[in]是否为子码流
 返回值：0:失败，非0:成功，返回值表示文件句柄,本头文件中，使用lRecrodHandle标识
 */
FUNCLIB_LIBRARY LONG_EX FC_Loc_StartRecordStreamEx(NetSDK_STREAM_AV_PARAM * pAvParam
                                ,const char * filePath
                                ,int nFileMaxSeconds
                                ,int nAllRecordMaxSeconds
                                ,int bIsSub
                                ,fRecFileNameCallBack cbRecFileNameCallBack
                                ,void *pUser);
/*
 函数名称：FC_Loc_OpenWrite
 函数功能：创建一个写MP4的文件，用于写数据
 参数说明：
            pAvParam:[in]编码参数
            filePath:[in]存储文件名
     nFileMaxSeconds:[in]输入参数 音频格式，支持AAC和G711
nAllRecordMaxSeconds:[in]最大录制时长
 返回值：0:失败，非0:成功，返回值表示文件句柄,本头文件中，使用lRecrodHandle标识
 */
FUNCLIB_LIBRARY LONG_EX FC_Loc_StartRecordStream(NetSDK_STREAM_AV_PARAM * pAvParam,const char * filePath
                              ,int nFileMaxSeconds,int nAllRecordMaxSeconds);

/*
 函数名称：FC_Loc_InputRecordStream
 函数功能：当采用FC_Loc_StartRecordStream模式进行录像时，传入要录制的视频数据
 参数说明：
         pFile:[in]写入的文件名
        pVideo:[in]输入参数 视频参数,仅支持H264和H265,不能为空
        pAudio:[in]输入参数 音频格式，支持AAC和G711
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_InputRecordStream(LONG_EX lRecrodHandle,const void * pBuffer,int nSize,int isVideo,int iskey,double timestamp);

/*
 函数名称：FC_Loc_StopRecordStream
 函数功能：当采用FC_Loc_StartRecordStream模式进行录像时，停止录像
 参数说明：
 lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_StopRecordStream(LONG_EX lRecrodHandle);

//replay
/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_GetReplayAblity(LONG_EX lDevItem);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_PlayDeviceFile(LONG_EX lDevItem,char * filenme);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_SetReplayDataCallBack(fRealDataCallBack cbReplayDataCallBack
                                 ,void *dwUser);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_SetPlayActionEventCallBack(fPlayActionEventCallBack cbActionCallback
                                      ,void *dwUser);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_ControlPlay(LONG_EX lDevItem,long Action,long param);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_SearchNVRRecByTime(LONG_EX lDevItem, long lChannel, char *pDate, int nIPCChannel);

/*
 函数名称：

 函数功能：

 参数说明：
        lDevItem:[in]设备标识
        lChannel:[in]如果是NVR设备，通道号
        pDate:[in]请求时间
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_SearchNVRRecByTimeEx(LONG_EX lDevItem, long lChannel, char *pDate, int nIPCChannel);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_NVRReplayByTime(LONG_EX lDevItem, long lChannel, char *pDateTime, unsigned int lRecordType, int nIPCChannel);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
        lFrameType: NVR倍速回放送帧类型，0->送全部帧，1->只送I帧
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_ControlNVRReplay(LONG_EX lDevItem, long lChannel, long lAction
                            , long lSpeed, long lFrameType, char *pPlayTime, int nIPCChannel);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_SetAUXResponseCallBack(AUXResponseCallBack fAUXCallBack,void * pUser);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_NVRRecordDownload(LONG_EX lDevItem, long lChannel, char *pStartTime
                             , char *pEndTime, char *pSaveFile, int nIPCChannel);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_NVRRecordDownloadStop(LONG_EX lDevItem, long lChannel, int nIPCChannel);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
//speak
FUNCLIB_LIBRARY int FC_Loc_StartSpeak(LONG_EX lDevItem, bool bTowWayCall);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_StopSpeak(LONG_EX lDevItem, bool bTowWayCall);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_InputSpeakAudioData(LONG_EX lDevItem, TPS_AudioData oAudioData);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_StopVoiceCom(LONG_EX lVoiceComHandle);

/*
 函数名称：

 函数功能：

 参数说明：
        lRecrodHandle:[in]调用FC_Loc_StartRecordStream时的标识句柄
 返回值：
        0:成功，非0:失败
 */
FUNCLIB_LIBRARY int FC_Loc_StartVoiceCom(LONG_EX lDevItem,unsigned long dwVoiceChan
                         ,bool bNeedCBNoEncData
                         ,fVoiceDataCallBack cbVoiceDataCallBack,void *pUser, bool bTowWayCall);

/*
 函数名称：FC_Loc_OpenWrite
 函数功能：创建一个写MP4的文件，用于写数据
 参数说明：
         pFile:[in]写入的文件名
        pVideo:[in]输入参数 视频参数,仅支持H264和H265,不能为空
        pAudio:[in]输入参数 音频格式，支持AAC和G711
 返回值：0:失败，非0:成功，返回值表示文件句柄
 */
FUNCLIB_LIBRARY MP4FILE_HANDLE	FC_Loc_OpenWrite(const char * pFile,NetSDK_VIDEO_PARAM * pVideo,NetSDK_AUDIO_PARAM * pAudio);

/*
 函数名称：FC_Loc_OpenRead
 函数功能：创建一个读取MP4的文件，用于读取数据
 参数说明：
         pFile:[in]读取的文件名
        pVideo:[out]输出参数 视频参数,仅支持H264和H265,不能为空
        pAudio:[out]输出参数 音频格式，支持AAC和G711,不能为空
 返回值：0:失败，非0:成功，返回值表示文件句柄
 */
FUNCLIB_LIBRARY MP4FILE_HANDLE	FC_Loc_OpenRead(const char * pFile,NetSDK_VIDEO_PARAM * pVideo,NetSDK_AUDIO_PARAM * pAudio);

/*
 函数名称：FC_Loc_GetMp4ReadWriteLastError
 函数功能：当调用FC_Loc_OpenWrite FC_Loc_OpenRead后，返回空时，调用此函数返回错误代码
 参数说明：
 返回值：0:无错误
        非0:成功，返回值表示文件句柄
 */
int     FC_Loc_GetMp4ReadWriteLastError();

/*
 函数名称:FC_Loc_CloseFile
 函数功能:关闭一个文件
 参数说明:
    fHandle:文件名柄
 返回值：0:成功，非0:失败
 */
FUNCLIB_LIBRARY int		FC_Loc_CloseFile(MP4FILE_HANDLE fHandle);

/*
 函数名称:FC_Loc_WriteOneFrame
 函数功能:写入一帧数据
 参数说明:
    fHandle:[in]文件名柄，必须是以FC_Loc_OpenWrite返回的文件句柄
    isvideo:[in]是否视频数据，1表示视频，0表示音频
    pBuffer:[in]媒体数据,数据必须是带00 00 00 01的数据头
    nInSize:[in]媒体数据长度
  timestamp:[in]当前视频的时截
      iskey:[in]是否关键帧，如果是音频，则都填1
 返回值：0:成功
     ERR_NOT_FIND_FILEHANDLE:文件句柄错误
     ERR_OUTOFF_MEMORY:内存不足
     其它非0:失败
 */
FUNCLIB_LIBRARY int		FC_Loc_WriteOneFrame(MP4FILE_HANDLE fHandle,int isvideo
                             ,const void * pBuffer,int nInSize
                             ,long long  timestamp,int iskey);

/*
 函数名称:FC_Loc_ReadOneFrame
 函数功能:读取一帧数据
 参数说明:
    fHandle:[in]文件名柄，必须是以FC_Loc_OpenRead返回的文件句柄
    isvideo:[out]是否视频数据，1表示视频，0表示音频
    pBuffer:[out]媒体数据指针
nMaxOutSize:[in out]媒体数据指针可存储的最大长度
  timestamp:[out]当前视频的时截
   duration:[out]当前帧时长
      iskey:[out]是否关键帧，如果是音频，则都填1
 返回值：0:成功
     ERR_NOT_FIND_FILEHANDLE:文件句柄错误
     ERR_OUTOFF_MEMORY:内存不足
     其它非0:失败
 */
#ifndef SDK_IOS
FUNCLIB_LIBRARY int	FC_Loc_ReadOneFrame(MP4FILE_HANDLE fHandle, int& isvideo, void** pBuffer, int& nMaxOutSize, unsigned long long& timestamp, unsigned long long& duration, int& iskey);
#endif
/*
 函数名称:FC_Loc_GetAllTime

 函数功能:获取读取的文件总时长，返回值以秒为单位

 参数说明:
    fHandle:[in]文件名柄，必须是以FC_Loc_OpenRead返回的文件句柄

 返回值：
                  大于0:表示返回文件长度
ERR_NOT_FIND_FILEHANDLE:句柄错误
      ERR_NOT_READMODE:文件句柄不是读取模式
                其它负值:失败
 */
FUNCLIB_LIBRARY int		FC_Loc_GetAllTime(MP4FILE_HANDLE fHandle);

/*
 函数名称:FC_Loc_GetNowTime
 函数功能:读取当前读取文件的位置，返回值以秒为单位
 参数说明:
    fHandle:[in]文件名柄，必须是以FC_Loc_OpenRead返回的文件句柄
 返回值：大于0，表示返回当前读取位置
       ERR_NOT_FIND_FILEHANDLE：句柄错误
        ERR_NOT_READMODE:文件句柄不是读取模式
       其它负值:失败
 */
FUNCLIB_LIBRARY int		FC_Loc_GetNowTime(MP4FILE_HANDLE fHandle);

/*
 函数名称:FC_Loc_SeekToFile
 函数功能:跳到指定位置进行读取
 参数说明:
     fHandle:[in]文件名柄，必须是以FC_Loc_OpenRead返回的文件句柄
    toSecond:[in]读取位置，单位为秒
 返回值：0:成功
       ERR_NOT_FIND_FILEHANDLE：句柄错误
        ERR_NOT_READMODE:文件句柄不是读取模式
       其它非0:失败
 */
FUNCLIB_LIBRARY int		FC_Loc_SeekToFile(MP4FILE_HANDLE fHandle,int toSecond);

/*
 函数名称:FC_Loc_MoveNextKeyFrame
 函数功能:跳至下一个视频关键帧
 参数说明:
     fHandle:[in]文件名柄，必须是以FC_Loc_OpenRead返回的文件句柄
 返回值：0:成功
       ERR_NOT_FIND_FILEHANDLE：句柄错误
        ERR_NOT_READMODE:文件句柄不是读取模式
       其它非0:失败
 */
FUNCLIB_LIBRARY int		FC_Loc_MoveNextKeyFrame(MP4FILE_HANDLE fHandle);

/*
 函数名称:FC_Loc_MovePrevKeyFrame
 函数功能:跳至上一个视频关键帧
 参数说明:
     fHandle:[in]文件名柄，必须是以FC_Loc_OpenRead返回的文件句柄
 返回值：0:成功
       ERR_NOT_FIND_FILEHANDLE：句柄错误
        ERR_NOT_READMODE:文件句柄不是读取模式
       其它非0:失败
 */
FUNCLIB_LIBRARY int		FC_Loc_MovePrevKeyFrame(MP4FILE_HANDLE fHandle);

/*
 函数名称:FC_Loc_GetRecordTimeFromFile
 函数功能:读取录像文件的总时长
 参数说明:
     pFileName:[in]文件名称，打开后会自动关闭，用于仅获取文件录像时长时使用
 返回值：大于0，表示录像文件的时长
        ERR_PARAM_ERROR:文件名错误
        ERR_OUTOFF_MEMORY:申请内存失败，系统内存不足
        ERR_OPEN_FILEERROR:打开文件失败
        ERR_MP4FILE_FORMAT_ERROR:读取文件失败，可能是文件格式错误
        其它非0:失败
 */
FUNCLIB_LIBRARY int		FC_Loc_GetRecordTimeFromFile(const char * pFileName);

/*
 函数名称：FC_Loc_SearchNvrRecByMonth
 函数功能：查询nvr录像，一个月的录像情况
 参数说明：pDevId：设备ID;pDate：查询日期，例如：“201709”
 返回值：0：成功，！＝0：失败
 注意：查询结果通过消息通知返回，用当月总天数(28,29等)个字符来表示，如：“201709:101010....”,'201709:':表示2017年9月的录像情况；‘1’:表示当天有录像，‘0’:表示当天无录像
 */
FUNCLIB_LIBRARY int FC_Loc_SearchNvrRecByMonth(LONG_EX lDevItem, long lChannel, char* pDate, int nIPCChannel);

/*
 函数名称：FC_IoTEncodeBindData
 函数功能：IoT型摄像机，配网过程中，将配网相关的数据进行加密发送给设备
 参数说明：
    resultData:  [out]输出参数 加密后的结果
    nSize:      [in] 输入参数 加密结果大小，建议为512个字节
    pSSID:      [in] 输入参数 路由器SSID
    pPassword:  [in] 输入参数 路由器密码
    pOwneruser: [in] 输入参数 APP用户名
    nLanguage:  [in] 输入参数 客户端所用语言
    nTimezone:  [in] 输入参数 客户端所在时区
 返回值：0：成功，-1：非法参数，-2：非法UTF字符
 注意：
 */
FUNCLIB_LIBRARY int FC_IoTEncodeBindData(char *resultData, int nSize, const char *pSSID, const char *pPassword, const char *pOwneruser, const char *pRandCode, int nLanguage, int nTimezone);

/*
 函数名称：FC_IoTCreateQRCode
 函数功能：IoT型摄像机，在扫描二维码绑定模式下创建二维码用
 参数说明：
    pQRCode:    [out]输出参数 二维码存放位置
    nSize:      [in] 输入参数 二维码存放大小，建议为512个字节
    pSSID:      [in] 输入参数 路由器SSID
    pPassword:  [in] 输入参数 路由器密码
    pOwneruser: [in] 输入参数 APP用户名
    nLanguage:  [in] 输入参数 客户端所用语言
    nTimezone:  [in] 输入参数 客户端所在时区
 返回值：0：成功，-1：非法参数，-2：非法UTF字符
 注意：
 */
FUNCLIB_LIBRARY int FC_IoTCreateQRCode(char *pQRCode, int nSize, const char *pSSID, const char *pPassword, const char *pOwneruser, const char *pRandCode, int nLanguage, int nTimezone);

/*
 函数名称：FC_IoTCreateSoundWave
 函数功能：IoT型摄像机，在声波绑定模式下创建声波用
 参数说明：
    pSoundWave: [out]输出参数 声波存放位置
    nSize:      [in] 输入参数 声波存放大小，建议为2*1024*1024个字节
    pSSID:      [in] 输入参数 路由器SSID
    pPassword:  [in] 输入参数 路由器密码
    pOwneruser: [in] 输入参数 APP用户名
    nLanguage:  [in] 输入参数 客户端所用语言
    nTimezone:  [in] 输入参数 客户端所在时区
    bSmartLink: [in] 输入参数 0:不发送SmartLink 1:发送SmartLink
 返回值：正值：生成的声波长度(以short单位计算)，非0：非法参数
 注意：
 */
FUNCLIB_LIBRARY int FC_IoTCreateSoundWave(char *pSoundWave, int nSize, const char *pSSID, const char *pPassword, const char *pOwneruser, const char *pRandCode, int nLanguage, int nTimezone, int bSmartLink);

/*
 函数名称：FC_IoTStopSmartLink
 函数功能：停止SmartLink动作
 参数说明：无
 返回值：无
 */
FUNCLIB_LIBRARY int FC_IoTStopSmartLink();

/*
 函数名称：FC_IoTGetDevComboInfo
 函数功能：查询设备套餐使用信息
 参数说明：pSerialNumber: 设备序列号，pDevType：all(所有类型),4g(4G流量),cs(云存储)， pICCID:设备SIM卡iccid
 返回值：成功返回0，否则返回以下错误码
 */
enum  {
    get_combo_info_error_user_not_login = -1206201,      //用户未登陆
    get_combo_info_error_parameter_invalid = -1206202,   //消息内容不全(没有iccid)
    get_combo_info_error_database = -1206203,            //连接数据库失败
    get_combo_info_error_from_benefitsystem = -1206204,  //从分润系统获取信息失败
    get_combo_info_error_user_not_add = -1206205,         //用户未添加设备，无权限查询
};
FUNCLIB_LIBRARY int FC_IoTGetDevComboInfo(char *pSerialNumber, char *pDevType, char *pICCID);

/*
 函数名称：FC_IoTGetTencentCloudStorageDetail
 函数功能：获取设备的腾讯云存详细信息
 参数说明：pSerialNumber: 设备序列号
 返回值：成功返回0，否则返回以下错误码
 */
enum  {
    get_tencentcloudstoragedetail_user_not_login = 600,      //用户未登陆
};
FUNCLIB_LIBRARY int FC_IoTGetTencentCloudStorageDetail(char *pSerialNumber);

/*
 函数名称：FC_IoTGetTencentCloudStorageDate
 函数功能：腾讯云存服务具有云存的日期
 参数说明：pSerialNumber: 设备序列号
 返回值：成功返回0，否则返回以下错误码
 */
enum  {
    get_tencentcloudstoragedate_user_not_login = 600,      //用户未登陆
};
FUNCLIB_LIBRARY int FC_IoTGetTencentCloudStorageDate(char *pSerialNumber);

/*
 函数名称：FC_IoTGetTencentCloudStorageTime
 函数功能：腾讯云存服务具有云存的时间轴
 参数说明：pSerialNumber: 设备序列号, pDate:日期，参数格式要求为yyyy-MM-dd 如2021-04-02, 
         nStartTime:开始时间戳单位秒（非必传）, nEndTime:结束时间戳单位秒（非必传）, pContext:接口调用上下文
 返回值：成功返回0，否则返回以下错误码
 */
enum  {
    get_tencentcloudstoragedetime_user_not_login = 600,      //用户未登陆
    get_tencentcloudstoragedetime_not_open_service = -1109009, //服务未开通
};
FUNCLIB_LIBRARY int FC_IoTGetTencentCloudStorageTime(char *pSerialNumber, char *pDate, int nStartTime, int nEndTime, char *pContext);

/*
 函数名称：FC_IoTGetTencentCloudStorageEvents
 函数功能：腾讯云存服务云存事件列表
 参数说明：pSerialNumber: 设备序列号, nStartTime:开始时间戳单位秒, nEndTime:结束时间戳单位秒, nSize:获取条数, pContext:接口调用上下文
        pEventId:事件类型
 返回值：成功返回0，否则返回以下错误码
 */
enum  {
    get_tencentcloudstoragedeevents_user_not_login = 600,      //用户未登陆
    get_tencentcloudstoragedeevents_not_open_service = -1109009, //服务未开通
};
FUNCLIB_LIBRARY int FC_IoTGetTencentCloudStorageEvents(char *pSerialNumber, int nStartTime, int nEndTime, int nSize, char *pContext, char *pEventId);


/*
 函数名称：FC_IoTGetTencentCloudStorageEventThumbnail
 函数功能：腾讯云存服务云存事件缩略图地址信息
 参数说明：pSerialNumber: 设备序列号, pThumbnail:缩略图文件名, pContext:接口调用上下文
 返回值：成功返回0，否则返回以下错误码
 */
enum  {
    get_tencentcloudstorageeventthumbnail_user_not_login = 600,      //用户未登陆
};
FUNCLIB_LIBRARY int FC_IoTGetTencentCloudStorageEventThumbnail(char *pSerialNumber, char *pThumbnail, char *pContext);

/*
 函数名称：FC_IoTGetTencentCloudStorageEncryptURL
 函数功能：腾讯云存服务云存视频播放地址转防盗链地址
 参数说明：pSerialNumber: 设备序列号, pOriginalURL: 设备序列号, nExpireTime:过期时间，设定过期时间点的10位时间戳值，
 返回值：成功返回0，否则返回以下错误码
 */
enum  {
    get_tencentcloudstorageencrypturl_user_not_login = 600,      //用户未登陆
};
FUNCLIB_LIBRARY int FC_IoTGetTencentCloudStorageEncryptURL(char *pSerialNumber, char *pOriginalURL, int nExpireTime);

/*
 函数名称：FC_IoTGetDevInfoAndConnectDev
 函数功能：根据序列号和校验码查询设备信息,并开始连接设备，连接成功回调TPS_MSG_P2P_CONNECT_OK，连接失败回调TPS_MSG_P2P_OFFLINE
 参数说明：pSerialNumber: 设备序列号，pVerifyCode：校验码
 返回值：查询设备信息成功返回云ID，否则返回以下错误码
 */
enum  {
    get_bind_info_error_dev_offline = -1206000,             //-1206000:设备不在线
    get_bind_info_error_user_not_login = -1206001,          //-1206001:用户未登陆
    get_bind_info_error_parameter_invalid = -1206002,       //-1206002:消息内容不全(没有sn或code)
    get_bind_info_error_no_create_verifycode = -1206003,    //-1206003:未生成校验码
    get_bind_info_error_verifycode = -1206004,              //-1206004:设备校验码错误
    get_bind_info_error_dev_id_no_exist = -1206005,         //-1206005:设备SN对应云ID不存在(设备尚未登录云平台)
    get_bind_info_error_dev_be_bound = -1206006,            //-1206006:设备已被绑定
    get_bind_info_error_dev_no_login = -1206007,            //-1206007:获取设备登录信息失败
    get_bind_info_error_other = -1206008,                   //-1206008:其他错误(连接数据库失败等)
    get_bind_info_error_tuya_connect_server = -1105400,     //-1105400:连接客户端服务失败
    get_bind_info_error_tuya_sync = -1105401,               //-1105401:获取涂鸦用户同步信息失败
    get_bind_info_error_tuya_connect_traceable = -1105402,  //-1105402:连接生产追溯系统失败
    get_bind_info_error_tuya_relation_uuid = -1105403,      //-1105403:设备关联涂鸦uuid 信息获取失败
    get_bind_info_error_tuya_already_bound = -1105404,      //-1105404 设备已经被其他用户绑定
    get_bind_info_error_tuya_connect = -1105405,            //-1105405 设备不在线 ，涂鸦mqtt 未连接
    get_bind_info_error_tuya_get_devlist = -1105406,        //-1105406 涂鸦平台获取设备列表失败
    get_bind_info_error_tuya_devid = -1105407,              //-1105407 涂鸦平台返回设备ID错误
    get_bind_info_error_tuya_bind = -1105408,               //-1105408 绑定失败,连续设备交互子系统同步绑定状态失败
};
FUNCLIB_LIBRARY int FC_IoTGetDevInfoAndConnectDev(char *pSerialNumber, char *pVerifyCode);
    
/*
 函数名称：FC_GetBindStatus
 函数功能：在设备绑定添加过程中查询当前的绑定进度
 参数说明：pSerialNumber: 设备序列号
 返回值：0:函数调用成功,
 */
enum  {
    bind_error_null = 0,            //0:设备绑定成功
    bind_error_user_not_login,      //-1205001:用户未登陆
    bind_error_parameter_invalid,   //-1205002:消息内容不全
    bind_error_unbind,              //-1205003:未绑定该设备
    bind_error_database_error,      //-1205004:连接数据库失败
    bind_error_user_not_exist,      //-1205005:APP用户不存在
    bind_error_sn_not_exist,        //-1205006:数据库中没有该序列号的设备
    bind_error_binded_by_other,     //-1205008:设备已被绑定
    bind_error_bind_time,           //-1205009:绑定时间错误
    bind_error_other,               //-1205007:其他错误
};
FUNCLIB_LIBRARY int FC_IoTGetBindStatus(int eBindType, char *pSerialNumber, char *pOwneruser);

/*
 函数名称：FC_IoTUnbindDevice
 函数功能：设备拥有者解除设备绑定状态
 参数说明：pSerialNumber: 设备序列号
 返回值：0:函数调用成功,
 */
enum  {
    unbind_error_null = 0,            //0:设备解除绑定成功
    unbind_error_user_not_login,      //-1305001:用户未登陆
    unbind_error_parameter_invalid,   //-1305002:消息内容不全
    unbind_error_unbind,              //-1305003:未绑定该设备
    unbind_error_database_error,      //-1305004:连接数据库失败
    unbind_error_user_not_exist,      //-1305005:APP用户不存在
    unbind_error_sn_not_exist,        //-1305006:数据库中没有该序列号的设备
    unbind_error_other,               //-1305007:其他错误
    unbind_error_connect_micro_server_error,//-1305008:连接微服务器失败
    unbind_error_micro_server_error,    //-1305009:微服务器错误
};
FUNCLIB_LIBRARY int FC_IoTUnbindDevice(char *pSerialNumber);

/*
 函数名称：FC_P2PIoTSystemControl
 函数功能：对设备进行高级系统控制
 参数说明：pDevId：设备ID nCommand：配置对应信息，请参考文档; pXml:配置xml文本内容
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
FUNCLIB_LIBRARY int FC_P2PIoTSystemControl(char* pDevId, int nCommand, char *pXml);

/*
 函数名称：FC_P2PIoTSystemControlWithPte
 函数功能：对IOT设备进行控制,走NVR透明通道
 参数说明：pDevId：设备ID nCommand：配置对应信息，请参考文档; pXml:配置xml文本内容 channel:透传通道号
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
FUNCLIB_LIBRARY int FC_P2PIoTSystemControlWithPte(char* pDevId, int nCommand, char *pXml, int nTransChannel);

/*
 函数名称：FC_Loc_IoTSystemControl
 函数功能：对设备进行高级系统控制(IoT设备专用)
 参数说明：lUserId：调用FC_LoginDev时的返回值; nCommand：配置对应信息，请参考文档; pXml:配置xml文本内容; nIPCChannel:枪球设备通道号，-1->非枪球设备，0->球通道，1->枪通道
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
FUNCLIB_LIBRARY int FC_Loc_IoTSystemControl(LONG_EX lDevItem, unsigned long nCmdValue, long flag, char *pXml, int nIPCChannel);

/*
 函数名称：FC_Loc_IoTBindDevice
 函数功能：IoT型摄像机，绑定设备用
 参数说明：lDevItem：设备ID
            pSSID：路由器SSID
            pPassword：路由器密码
            pOwneruser：APP用户名
            pOwnerpass：APP密码
            bBindForce：是否强制绑定(0：正常绑定流程，1：不用测速直接强制绑定)
 返回值：0：成功，！＝0：失败
 注意：
 */
FUNCLIB_LIBRARY int FC_Loc_IoTBindDevice(LONG_EX lDevItem, char *pSSID, char *pPassword, char *pOwneruser, char *pOwnerpass, int bBindForce);

/*
 函数名称：FC_P2P_IoTBindDevice
 函数功能：IoT型摄像机，绑定设备用
 参数说明：pDevId：设备云ID，pOwneruser：APP用户名，pOwnerpass：APP密码，bBindForce：是否强制绑定(0：正常绑定流程，1：不用测速直接强制绑定)
 返回值：0：成功，！＝0：失败
 注意：
 */
FUNCLIB_LIBRARY int FC_P2P_IoTBindDevice(char* pDevId, char *pOwneruser, char *pOwnerpass, int bBindForce);
    
/*
 函数名称：FC_Loc_IoTTimeSync
 函数功能：IoT型摄像机，在AP模式下将手机时间同步到设备时用
 参数说明：lDevItem：设备ID
 返回值：0：成功，！＝0：失败
 注意：
 */
FUNCLIB_LIBRARY int FC_Loc_IoTTimeSync(LONG_EX lDevItem);

    
/*
 函数名称：FC_StartSearchIotBindingStatus
 函数功能：开始查询IOT设备绑定状态
 参数说明：无
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_Loc_StartSearchIotBindingStatus();
    
/*
 函数名称：FC_StopSearchIotBindingStatus
 函数功能：停止查询IOT设备绑定状态
 参数说明：无
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_Loc_StopSearchIotBindingStatus();

/*
 函数名称：FC_SetSearchIotBindStateCallBack
 函数功能：设置查询IOT设备绑定状态广播包响应回调函数
 参数说明：fSearchIotBindCallBack：搜索回调响应函数
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_Loc_SetSearchIotBindStateCallBack(SearchIotBindStateCallBack fSearchIotBindCallBack);

/*
 函数名称：FC_P2P_DevSystemControlReq
 函数功能：对设备进行高级系统控制
 参数说明：pDevId：        设备ID 
           nMsgType：消息类型，请查看TPS_MSG_TYPE定义
           nMsgCode：消息ID码，请参考文档
           nMsgFlag：消息标志位
           pMsgUuid：消息UUID，消息头不需要携带UUID则可以置NULL
           pXml：     配置xml文本内容
 返回值：0:函数调用成功；具体的响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
 */
//消息事件类型定义
enum TPS_MSG_TYPE {
    TPS_MSG_TYPE_BASE = 0, 
    TPS_MSG_TYPE_SYSTEM_CONFIG_GET,                                 // SYSTEM_CONFIG_GET_MESSAGE
    TPS_MSG_TYPE_SYSTEM_CONFIG_SET,                                 // SYSTEM_CONFIG_SET_MESSAGE
    TPS_MSG_TYPE_SYSTEM_CONTROL,                                    // SYSTEM_CONTROL_MESSAGE
    TPS_MSG_TYPE_SYSTEM_HWCFG,                                      // SYSTEM_HWCFG_MESSAGE
    TPS_MSG_TYPE_LIVE_STREAM_MESSAGE,                               // LIVE_STREAM_MESSAGE
    TPS_MSG_TYPE_MEDIA_DATA_MESSAGE,                                // MEDIA_DATA_MESSAGE
    TPS_MSG_TYPE_IOT_CAMERA = TPS_MSG_TYPE_BASE + 100,              // IOT_CAMERA_MESSAGE, IOT Camera message start
    TPS_MSG_TYPE_NVR_REPLAY = TPS_MSG_TYPE_BASE + 200,              // NVR_REPLAY_MESSAGE, IOT Relay message start
    TPS_MSG_TYPE_MAX
};
FUNCLIB_LIBRARY int FC_P2P_DevSystemControlReq(char* pDevId, int nMsgType, int nMsgCode, int nMsgFlag, char *pMsgUuid, char *pXml);

/*
 函数名称：FC_StartSpeedTest
 函数功能：
 参数说明：pPath：服务器列表文件保存路径，lat：客户端所在纬度，lon：客户端所在经度，nLanguage：客户端所用语言
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_StartSpeedTest(const char *pPath, float lat, float lon, int nLanguage);

/*
 函数名称：FC_StopSpeedTest
 函数功能：
 参数说明：无
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_StopSpeedTest();

/*
 函数名称：FC_GetUserIDInfo
 函数功能：获取用户ID、phpsessionid等信息
 参数说明：pSvrDomian：输出参数建议256字节，pSessionId：输出参数建议256字节，pUserId：输出参数建议256字节，
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_GetUserIDInfo(char *pSvrDomian, char *pSessionId, char *pUserId);

/*
 函数名称：FC_GetP2PTrafficData
 函数功能：P2P流量使用统计
 参数说明：无
 返回值：>=0:字节数KB <0:调用失败
 */
FUNCLIB_LIBRARY int FC_GetP2PTrafficData();

/*
 函数名称：FC_GetH5AuthInfo
 函数功能：获取与H5页面交互的鉴权信息
 参数说明：FC_GetH5AuthInfo：输出参数建议256字节
 返回值：>=0:函数调用成功；<0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_GetH5AuthInfo(char *pAuthInfo);

/*
 函数名称：FC_WexinOnceSubscription
 函数功能：发送微信一次订阅消息
 参数说明：pOpenId:用户唯一标识 pTemplateId:订阅消息模板 ID nScene:场景值
 返回值：0:函数调用成功；非0:函数调用失败
 */
FUNCLIB_LIBRARY int FC_WexinOnceSubscription(const char *pOpenId, const char *pTemplateId, int nScene);

/*
 函数名称：FC_MsgList
 函数功能：获取消息列表接口
 参数说明：requestBody 使用json字符串，内容如下
 {
 operationType 操作类型  1：获取新消息  2：获取历史消息
 msgType       消息类型  1：系统消息    2：活动消息
 offsetId      偏移id
 size          查询数量
 }

 返回值：200：成功，非200:失败
 回调消息：TPS_MSG_GET_MSG_LIST
 */
FUNCLIB_LIBRARY int FC_MsgList(const char *requestBody);

/*
 函数名称：FC_MsgUnreadCount
 函数功能：获取未读消息数量
 参数说明：无
 返回值：200：成功，非200:失败
 回调消息：TPS_MSG_GET_MSG_UNREAD_COUNT
 */
FUNCLIB_LIBRARY int FC_MsgUnreadCount();

/*
 函数名称：FC_MsgUpdateRead
 函数功能：更新消息已读状态
 参数说明：requestBody 使用json字符串，内容如下
 {
 bizId  消息业务id
 }

 返回值：200：成功，非200:失败
 */
FUNCLIB_LIBRARY int FC_MsgUpdateRead(const char *requestBody);

/*
 函数名称：FC_MsgAllRead
 函数功能：设置消息全部已读状态
 参数说明：无
 返回值：200：成功，非200:失败
 */
FUNCLIB_LIBRARY int FC_MsgAllRead();

/*
 函数名称：FC_MsgDelete
 函数功能：站内信消息批量删除
 参数说明：requestBody 使用json字符串，如{"ids":"2328,2285"}
 返回值：200：成功，非200:失败
 */
FUNCLIB_LIBRARY int FC_MsgDelete(const char *requestBody);

/*
 函数名称：FC_ActivateSimCard
 函数功能：向服务器请求激活sim卡
 参数说明：iccid:需要激活的卡号 cardtype:设备卡类型：0 单卡，1 双卡。默认为 0,不传入此参数以单卡类型处理
 返回值：200：成功，非200:失败
 */
FUNCLIB_LIBRARY int FC_ActivateSimCard(const char *iccid, int cardtype);

/*
 函数名称：FC_UploadCtrlDevLog
 函数功能：向服务器上报APP远程操作日志
 参数说明：log:操作日志，内容为JSON字符串：{deviceId:设备云ID deviceSn:设备序列号 operateLog:日志内容}
 返回值：200：成功，非200:失败
 */
FUNCLIB_LIBRARY int FC_UploadCtrlDevLog(const char *log);

/*
 函数名称：FC_GetTrustedDevList
 函数功能：获取托管设备列表
 参数说明：无
 返回值：200：成功，非200:失败
 回调消息：TPS_MSG_RSP_TRUSTED_DEV_LIST
 */
FUNCLIB_LIBRARY int FC_GetTrustedDevList();

/*
 函数名称：FC_GetTrustedDevAndConnect
 函数功能：获取托管设备详情并且连接设备
 参数说明：{deviceSn:""}
 返回值：200：成功，非200:失败
 回调消息：TPS_MSG_RSP_TRUSTED_DEV_DETAIL
 */
FUNCLIB_LIBRARY int FC_GetTrustedDevAndConnect(const char *deviceSn, const char *testJson);

typedef enum {
    HTTP_REQUEST_TYPE_GET,
    HTTP_REQUEST_TYPE_POST,
}HTTP_REQUEST_TYPE;

typedef enum {
    SERVER_DOMAIN_USER,
    SERVER_DOMAIN_BIZ,
} SERVER_DOMAIN_TYPE;


FUNCLIB_LIBRARY int FC_HttpRequest(HTTP_REQUEST_TYPE requestType, SERVER_DOMAIN_TYPE domainType, const char *path, const char *param, char **respData);

FUNCLIB_LIBRARY int FC_SetAccessToken(const char *accessToken, const char *refreshToken, const char *bizDomain, const char *bizDomainBack, unsigned long accessTokenExp);

FUNCLIB_LIBRARY void FC_MD5Password(char *pSrcPsw, char *pNewPsw);

FUNCLIB_LIBRARY int FC_AddDeviceStream(const char *devList);

FUNCLIB_LIBRARY int FC_SetUserInfo2(const char *userInfo);

FUNCLIB_LIBRARY int FC_SetP2pServerList(const char *p2pServerList);

FUNCLIB_LIBRARY int FC_DecodeString(char *pInput, int putLen,  char *pOutPutBuf, int bufLen);

FUNCLIB_LIBRARY int FC_EncodeString(char *pInput, char *pOutPutBuf, int bufLen);

#ifdef __cplusplus
}
#endif

#endif



