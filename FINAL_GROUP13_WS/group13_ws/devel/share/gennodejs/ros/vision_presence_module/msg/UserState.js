// Auto-generated. Do not edit!

// (in-package vision_presence_module.msg)


"use strict";

const _serializer = _ros_msg_utils.Serialize;
const _arraySerializer = _serializer.Array;
const _deserializer = _ros_msg_utils.Deserialize;
const _arrayDeserializer = _deserializer.Array;
const _finder = _ros_msg_utils.Find;
const _getByteLength = _ros_msg_utils.getByteLength;

//-----------------------------------------------------------

class UserState {
  constructor(initObj={}) {
    if (initObj === null) {
      // initObj === null is a special case for deserialization where we don't initialize fields
      this.user_present = null;
      this.consecutive_eyes_missing = null;
      this.consecutive_face_absent = null;
      this.stamp = null;
    }
    else {
      if (initObj.hasOwnProperty('user_present')) {
        this.user_present = initObj.user_present
      }
      else {
        this.user_present = false;
      }
      if (initObj.hasOwnProperty('consecutive_eyes_missing')) {
        this.consecutive_eyes_missing = initObj.consecutive_eyes_missing
      }
      else {
        this.consecutive_eyes_missing = 0;
      }
      if (initObj.hasOwnProperty('consecutive_face_absent')) {
        this.consecutive_face_absent = initObj.consecutive_face_absent
      }
      else {
        this.consecutive_face_absent = 0;
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
    // Serializes a message object of type UserState
    // Serialize message field [user_present]
    bufferOffset = _serializer.bool(obj.user_present, buffer, bufferOffset);
    // Serialize message field [consecutive_eyes_missing]
    bufferOffset = _serializer.int32(obj.consecutive_eyes_missing, buffer, bufferOffset);
    // Serialize message field [consecutive_face_absent]
    bufferOffset = _serializer.int32(obj.consecutive_face_absent, buffer, bufferOffset);
    // Serialize message field [stamp]
    bufferOffset = _serializer.time(obj.stamp, buffer, bufferOffset);
    return bufferOffset;
  }

  static deserialize(buffer, bufferOffset=[0]) {
    //deserializes a message object of type UserState
    let len;
    let data = new UserState(null);
    // Deserialize message field [user_present]
    data.user_present = _deserializer.bool(buffer, bufferOffset);
    // Deserialize message field [consecutive_eyes_missing]
    data.consecutive_eyes_missing = _deserializer.int32(buffer, bufferOffset);
    // Deserialize message field [consecutive_face_absent]
    data.consecutive_face_absent = _deserializer.int32(buffer, bufferOffset);
    // Deserialize message field [stamp]
    data.stamp = _deserializer.time(buffer, bufferOffset);
    return data;
  }

  static getMessageSize(object) {
    return 17;
  }

  static datatype() {
    // Returns string type for a message object
    return 'vision_presence_module/UserState';
  }

  static md5sum() {
    //Returns md5sum for a message object
    return '073fb340af5920b5f6f7b52a6f27778e';
  }

  static messageDefinition() {
    // Returns full string definition for message
    return `
    bool  user_present
    int32 consecutive_eyes_missing
    int32 consecutive_face_absent
    time  stamp
    
    `;
  }

  static Resolve(msg) {
    // deep-construct a valid message object instance of whatever was passed in
    if (typeof msg !== 'object' || msg === null) {
      msg = {};
    }
    const resolved = new UserState(null);
    if (msg.user_present !== undefined) {
      resolved.user_present = msg.user_present;
    }
    else {
      resolved.user_present = false
    }

    if (msg.consecutive_eyes_missing !== undefined) {
      resolved.consecutive_eyes_missing = msg.consecutive_eyes_missing;
    }
    else {
      resolved.consecutive_eyes_missing = 0
    }

    if (msg.consecutive_face_absent !== undefined) {
      resolved.consecutive_face_absent = msg.consecutive_face_absent;
    }
    else {
      resolved.consecutive_face_absent = 0
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

module.exports = UserState;
