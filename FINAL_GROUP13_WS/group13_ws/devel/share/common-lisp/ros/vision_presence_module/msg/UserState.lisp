; Auto-generated. Do not edit!


(cl:in-package vision_presence_module-msg)


;//! \htmlinclude UserState.msg.html

(cl:defclass <UserState> (roslisp-msg-protocol:ros-message)
  ((user_present
    :reader user_present
    :initarg :user_present
    :type cl:boolean
    :initform cl:nil)
   (consecutive_eyes_missing
    :reader consecutive_eyes_missing
    :initarg :consecutive_eyes_missing
    :type cl:integer
    :initform 0)
   (consecutive_face_absent
    :reader consecutive_face_absent
    :initarg :consecutive_face_absent
    :type cl:integer
    :initform 0)
   (stamp
    :reader stamp
    :initarg :stamp
    :type cl:real
    :initform 0))
)

(cl:defclass UserState (<UserState>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <UserState>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'UserState)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name vision_presence_module-msg:<UserState> is deprecated: use vision_presence_module-msg:UserState instead.")))

(cl:ensure-generic-function 'user_present-val :lambda-list '(m))
(cl:defmethod user_present-val ((m <UserState>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader vision_presence_module-msg:user_present-val is deprecated.  Use vision_presence_module-msg:user_present instead.")
  (user_present m))

(cl:ensure-generic-function 'consecutive_eyes_missing-val :lambda-list '(m))
(cl:defmethod consecutive_eyes_missing-val ((m <UserState>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader vision_presence_module-msg:consecutive_eyes_missing-val is deprecated.  Use vision_presence_module-msg:consecutive_eyes_missing instead.")
  (consecutive_eyes_missing m))

(cl:ensure-generic-function 'consecutive_face_absent-val :lambda-list '(m))
(cl:defmethod consecutive_face_absent-val ((m <UserState>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader vision_presence_module-msg:consecutive_face_absent-val is deprecated.  Use vision_presence_module-msg:consecutive_face_absent instead.")
  (consecutive_face_absent m))

(cl:ensure-generic-function 'stamp-val :lambda-list '(m))
(cl:defmethod stamp-val ((m <UserState>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader vision_presence_module-msg:stamp-val is deprecated.  Use vision_presence_module-msg:stamp instead.")
  (stamp m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <UserState>) ostream)
  "Serializes a message object of type '<UserState>"
  (cl:write-byte (cl:ldb (cl:byte 8 0) (cl:if (cl:slot-value msg 'user_present) 1 0)) ostream)
  (cl:let* ((signed (cl:slot-value msg 'consecutive_eyes_missing)) (unsigned (cl:if (cl:< signed 0) (cl:+ signed 4294967296) signed)))
    (cl:write-byte (cl:ldb (cl:byte 8 0) unsigned) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) unsigned) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) unsigned) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) unsigned) ostream)
    )
  (cl:let* ((signed (cl:slot-value msg 'consecutive_face_absent)) (unsigned (cl:if (cl:< signed 0) (cl:+ signed 4294967296) signed)))
    (cl:write-byte (cl:ldb (cl:byte 8 0) unsigned) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) unsigned) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) unsigned) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) unsigned) ostream)
    )
  (cl:let ((__sec (cl:floor (cl:slot-value msg 'stamp)))
        (__nsec (cl:round (cl:* 1e9 (cl:- (cl:slot-value msg 'stamp) (cl:floor (cl:slot-value msg 'stamp)))))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) __sec) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) __sec) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) __sec) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) __sec) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 0) __nsec) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) __nsec) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) __nsec) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) __nsec) ostream))
)
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <UserState>) istream)
  "Deserializes a message object of type '<UserState>"
    (cl:setf (cl:slot-value msg 'user_present) (cl:not (cl:zerop (cl:read-byte istream))))
    (cl:let ((unsigned 0))
      (cl:setf (cl:ldb (cl:byte 8 0) unsigned) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) unsigned) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) unsigned) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) unsigned) (cl:read-byte istream))
      (cl:setf (cl:slot-value msg 'consecutive_eyes_missing) (cl:if (cl:< unsigned 2147483648) unsigned (cl:- unsigned 4294967296))))
    (cl:let ((unsigned 0))
      (cl:setf (cl:ldb (cl:byte 8 0) unsigned) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) unsigned) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) unsigned) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) unsigned) (cl:read-byte istream))
      (cl:setf (cl:slot-value msg 'consecutive_face_absent) (cl:if (cl:< unsigned 2147483648) unsigned (cl:- unsigned 4294967296))))
    (cl:let ((__sec 0) (__nsec 0))
      (cl:setf (cl:ldb (cl:byte 8 0) __sec) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) __sec) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) __sec) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) __sec) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 0) __nsec) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) __nsec) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) __nsec) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) __nsec) (cl:read-byte istream))
      (cl:setf (cl:slot-value msg 'stamp) (cl:+ (cl:coerce __sec 'cl:double-float) (cl:/ __nsec 1e9))))
  msg
)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<UserState>)))
  "Returns string type for a message object of type '<UserState>"
  "vision_presence_module/UserState")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'UserState)))
  "Returns string type for a message object of type 'UserState"
  "vision_presence_module/UserState")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<UserState>)))
  "Returns md5sum for a message object of type '<UserState>"
  "073fb340af5920b5f6f7b52a6f27778e")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'UserState)))
  "Returns md5sum for a message object of type 'UserState"
  "073fb340af5920b5f6f7b52a6f27778e")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<UserState>)))
  "Returns full string definition for message of type '<UserState>"
  (cl:format cl:nil "bool  user_present~%int32 consecutive_eyes_missing~%int32 consecutive_face_absent~%time  stamp~%~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'UserState)))
  "Returns full string definition for message of type 'UserState"
  (cl:format cl:nil "bool  user_present~%int32 consecutive_eyes_missing~%int32 consecutive_face_absent~%time  stamp~%~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <UserState>))
  (cl:+ 0
     1
     4
     4
     8
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <UserState>))
  "Converts a ROS message object to a list"
  (cl:list 'UserState
    (cl:cons ':user_present (user_present msg))
    (cl:cons ':consecutive_eyes_missing (consecutive_eyes_missing msg))
    (cl:cons ':consecutive_face_absent (consecutive_face_absent msg))
    (cl:cons ':stamp (stamp msg))
))
