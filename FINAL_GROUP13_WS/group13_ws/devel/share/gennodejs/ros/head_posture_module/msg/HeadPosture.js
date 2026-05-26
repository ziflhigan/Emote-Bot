// Auto-generated. Do not edit!

// (in-package head_posture_module.msg)


"use strict";

const _serializer = _ros_msg_utils.Serialize;
const _arraySerializer = _serializer.Array;
const _deserializer = _ros_msg_utils.Deserialize;
const _arrayDeserializer = _deserializer.Array;
const _finder = _ros_msg_utils.Find;
const _getByteLength = _ros_msg_utils.getByteLength;

//-----------------------------------------------------------

class HeadPosture {
  constructor(initObj={}) {
    if (initObj === null) {
      // initObj === null is a special case for deserialization where we don't initialize fields
      this.pose_visible = null;
      this.calibrated = null;
      this.head_down = null;
      this.posture_score = null;
      this.head_drop_ratio = null;
      this.baseline_ratio = null;
      this.consecutive_droop_frames = null;
      this.stamp = null;
    }
    else {
      if (initObj.hasOwnProperty('pose_visible')) {
        this.pose_visible = initObj.pose_visible
      }
      else {
        this.pose_visible = false;
      }
      if (initObj.hasOwnProperty('calibrated')) {
        this.calibrated = initObj.calibrated
      }
      else {
        this.calibrated = false;
      }
      if (initObj.hasOwnProperty('head_down')) {
        this.head_down = initObj.head_down
      }
      else {
        this.head_down = false;
      }
      if (initObj.hasOwnProperty('posture_score')) {
        this.posture_score = initObj.posture_score
      }
      else {
        this.posture_score = 0.0;
      }
      if (initObj.hasOwnProperty('head_drop_ratio')) {
        this.head_drop_ratio = initObj.head_drop_ratio
      }
      else {
        this.head_drop_ratio = 0.0;
      }
      if (initObj.hasOwnProperty('baseline_ratio')) {
        this.baseline_ratio = initObj.baseline_ratio
      }
      else {
        this.baseline_ratio = 0.0;
      }
      if (initObj.hasOwnProperty('consecutive_droop_frames')) {
        this.consecutive_droop_frames = initObj.consecutive_droop_frames
      }
      else {
        this.consecutive_droop_frames = 0;
      }
      if (initObj.hasOwnProperty('stamp')) {
        this.stamp = initObj.stamp
      }
      else {
        this.stamp = {secs: 0, nsecs: 0};
      }
    }
  }

  static serialize(obj, buffer, bufferOffset) {
    // Serializes a message object of type HeadPosture
    // Serialize message field [pose_visible]
    bufferOffset = _serializer.bool(obj.pose_visible, buffer, bufferOffset);
    // Serialize message field [calibrated]
    bufferOffset = _serializer.bool(obj.calibrated, buffer, bufferOffset);
    // Serialize message field [head_down]
    bufferOffset = _serializer.bool(obj.head_down, buffer, bufferOffset);
    // Serialize message field [posture_score]
    bufferOffset = _serializer.float32(obj.posture_score, buffer, bufferOffset);
    // Serialize message field [head_drop_ratio]
    bufferOffset = _serializer.float32(obj.head_drop_ratio, buffer, bufferOffset);
    // Serialize message field [baseline_ratio]
    bufferOffset = _serializer.float32(obj.baseline_ratio, buffer, bufferOffset);
    // Serialize message field [consecutive_droop_frames]
    bufferOffset = _serializer.int32(obj.consecutive_droop_frames, buffer, bufferOffset);
    // Serialize message field [stamp]
    bufferOffset = _serializer.time(obj.stamp, buffer, bufferOffset);
    return bufferOffset;
  }

  static deserialize(buffer, bufferOffset=[0]) {
    //deserializes a message object of type HeadPosture
    let len;
    let data = new HeadPosture(null);
    // Deserialize message field [pose_visible]
    data.pose_visible = _deserializer.bool(buffer, bufferOffset);
    // Deserialize message field [calibrated]
    data.calibrated = _deserializer.bool(buffer, bufferOffset);
    // Deserialize message field [head_down]
    data.head_down = _deserializer.bool(buffer, bufferOffset);
    // Deserialize message field [posture_score]
    data.posture_score = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [head_drop_ratio]
    data.head_drop_ratio = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [baseline_ratio]
    data.baseline_ratio = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [consecutive_droop_frames]
    data.consecutive_droop_frames = _deserializer.int32(buffer, bufferOffset);
    // Deserialize message field [stamp]
    data.stamp = _deserializer.time(buffer, bufferOffset);
    return data;
  }

  static getMessageSize(object) {
    return 27;
  }

  static datatype() {
    // Returns string type for a message object
    return 'head_posture_module/HeadPosture';
  }

  static md5sum() {
    //Returns md5sum for a message object
    return 'cf8798f74ba00625c0c934cef96b9d09';
  }

  static messageDefinition() {
    // Returns full string definition for message
    return `
    # Head posture evidence from the MediaPipe pose node.
    # Input to the fatigue monitor; does not trigger speech by itself.
    
    bool pose_visible
    bool calibrated
    bool head_down
    
    float32 posture_score
    float32 head_drop_ratio
    float32 baseline_ratio
    
    int32 consecutive_droop_frames
    time stamp
    
    `;
  }

  static Resolve(msg) {
    // deep-construct a valid message object instance of whatever was passed in
    if (typeof msg !== 'object' || msg === null) {
      msg = {};
    }
    const resolved = new HeadPosture(null);
    if (msg.pose_visible !== undefined) {
      resolved.pose_visible = msg.pose_visible;
    }
    else {
      resolved.pose_visible = false
    }

    if (msg.calibrated !== undefined) {
      resolved.calibrated = msg.calibrated;
    }
    else {
      resolved.calibrated = false
    }

    if (msg.head_down !== undefined) {
      resolved.head_down = msg.head_down;
    }
    else {
      resolved.head_down = false
    }

    if (msg.posture_score !== undefined) {
      resolved.posture_score = msg.posture_score;
    }
    else {
      resolved.posture_score = 0.0
    }

    if (msg.head_drop_ratio !== undefined) {
      resolved.head_drop_ratio = msg.head_drop_ratio;
    }
    else {
      resolved.head_drop_ratio = 0.0
    }

    if (msg.baseline_ratio !== undefined) {
      resolved.baseline_ratio = msg.baseline_ratio;
    }
    else {
      resolved.baseline_ratio = 0.0
    }

    if (msg.consecutive_droop_frames !== undefined) {
      resolved.consecutive_droop_frames = msg.consecutive_droop_frames;
    }
    else {
      resolved.consecutive_droop_frames = 0
    }

    if (msg.stamp !== undefined) {
      resolved.stamp = msg.stamp;
    }
    else {
      resolved.stamp = {secs: 0, nsecs: 0}
    }

    return resolved;
    }
};

module.exports = HeadPosture;
