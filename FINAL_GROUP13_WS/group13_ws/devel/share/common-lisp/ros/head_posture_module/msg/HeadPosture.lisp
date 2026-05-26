; Auto-generated. Do not edit!


(cl:in-package head_posture_module-msg)


;//! \htmlinclude HeadPosture.msg.html

(cl:defclass <HeadPosture> (roslisp-msg-protocol:ros-message)
  ((pose_visible
    :reader pose_visible
    :initarg :pose_visible
    :type cl:boolean
    :initform cl:nil)
   (calibrated
    :reader calibrated
    :initarg :calibrated
    :type cl:boolean
    :initform cl:nil)
   (head_down
    :reader head_down
    :initarg :head_down
    :type cl:boolean
    :initform cl:nil)
   (posture_score
    :reader posture_score
    :initarg :posture_score
    :type cl:float
    :initform 0.0)
   (head_drop_ratio
    :reader head_drop_ratio
    :initarg :head_drop_ratio
    :type cl:float
    :initform 0.0)
   (baseline_ratio
    :reader baseline_ratio
    :initarg :baseline_ratio
    :type cl:float
    :initform 0.0)
   (consecutive_droop_frames
    :reader consecutive_droop_frames
    :initarg :consecutive_droop_frames
    :type cl:integer
    :initform 0)
   (stamp
    :reader stamp
    :initarg :stamp
    :type cl:real
    :initform 0))
)

(cl:defclass HeadPosture (<HeadPosture>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <HeadPosture>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'HeadPosture)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name head_posture_module-msg:<HeadPosture> is deprecated: use head_posture_module-msg:HeadPosture instead.")))

(cl:ensure-generic-function 'pose_visible-val :lambda-list '(m))
(cl:defmethod pose_visible-val ((m <HeadPosture>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader head_posture_module-msg:pose_visible-val is deprecated.  Use head_posture_module-msg:pose_visible instead.")
  (pose_visible m))

(cl:ensure-generic-function 'calibrated-val :lambda-list '(m))
(cl:defmethod calibrated-val ((m <HeadPosture>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader head_posture_module-msg:calibrated-val is deprecated.  Use head_posture_module-msg:calibrated instead.")
  (calibrated m))

(cl:ensure-generic-function 'head_down-val :lambda-list '(m))
(cl:defmethod head_down-val ((m <HeadPosture>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader head_posture_module-msg:head_down-val is deprecated.  Use head_posture_module-msg:head_down instead.")
  (head_down m))

(cl:ensure-generic-function 'posture_score-val :lambda-list '(m))
(cl:defmethod posture_score-val ((m <HeadPosture>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader head_posture_module-msg:posture_score-val is deprecated.  Use head_posture_module-msg:posture_score instead.")
  (posture_score m))

(cl:ensure-generic-function 'head_drop_ratio-val :lambda-list '(m))
(cl:defmethod head_drop_ratio-val ((m <HeadPosture>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader head_posture_module-msg:head_drop_ratio-val is deprecated.  Use head_posture_module-msg:head_drop_ratio instead.")
  (head_drop_ratio m))

(cl:ensure-generic-function 'baseline_ratio-val :lambda-list '(m))
(cl:defmethod baseline_ratio-val ((m <HeadPosture>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader head_posture_module-msg:baseline_ratio-val is deprecated.  Use head_posture_module-msg:baseline_ratio instead.")
  (baseline_ratio m))

(cl:ensure-generic-function 'consecutive_droop_frames-val :lambda-list '(m))
(cl:defmethod consecutive_droop_frames-val ((m <HeadPosture>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader head_posture_module-msg:consecutive_droop_frames-val is deprecated.  Use head_posture_module-msg:consecutive_droop_frames instead.")
  (consecutive_droop_frames m))

(cl:ensure-generic-function 'stamp-val :lambda-list '(m))
(cl:defmethod stamp-val ((m <HeadPosture>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader head_posture_module-msg:stamp-val is deprecated.  Use head_posture_module-msg:stamp instead.")
  (stamp m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <HeadPosture>) ostream)
  "Serializes a message object of type '<HeadPosture>"
  (cl:write-byte (cl:ldb (cl:byte 8 0) (cl:if (cl:slot-value msg 'pose_visible) 1 0)) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 0) (cl:if (cl:slot-value msg 'calibrated) 1 0)) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 0) (cl:if (cl:slot-value msg 'head_down) 1 0)) ostream)
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'posture_score))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'head_drop_ratio))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'baseline_ratio))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let* ((signed (cl:slot-value msg 'consecutive_droop_frames)) (unsigned (cl:if (cl:< signed 0) (cl:+ signed 4294967296) signed)))
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
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <HeadPosture>) istream)
  "Deserializes a message object of type '<HeadPosture>"
    (cl:setf (cl:slot-value msg 'pose_visible) (cl:not (cl:zerop (cl:read-byte istream))))
    (cl:setf (cl:slot-value msg 'calibrated) (cl:not (cl:zerop (cl:read-byte istream))))
    (cl:setf (cl:slot-value msg 'head_down) (cl:not (cl:zerop (cl:read-byte istream))))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'posture_score) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'head_drop_ratio) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'baseline_ratio) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((unsigned 0))
      (cl:setf (cl:ldb (cl:byte 8 0) unsigned) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) unsigned) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) unsigned) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) unsigned) (cl:read-byte istream))
      (cl:setf (cl:slot-value msg 'consecutive_droop_frames) (cl:if (cl:< unsigned 2147483648) unsigned (cl:- unsigned 4294967296))))
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
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<HeadPosture>)))
  "Returns string type for a message object of type '<HeadPosture>"
  "head_posture_module/HeadPosture")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'HeadPosture)))
  "Returns string type for a message object of type 'HeadPosture"
  "head_posture_module/HeadPosture")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<HeadPosture>)))
  "Returns md5sum for a message object of type '<HeadPosture>"
  "cf8798f74ba00625c0c934cef96b9d09")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'HeadPosture)))
  "Returns md5sum for a message object of type 'HeadPosture"
  "cf8798f74ba00625c0c934cef96b9d09")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<HeadPosture>)))
  "Returns full string definition for message of type '<HeadPosture>"
  (cl:format cl:nil "# Head posture evidence from the MediaPipe pose node.~%# Input to the fatigue monitor; does not trigger speech by itself.~%~%bool pose_visible~%bool calibrated~%bool head_down~%~%float32 posture_score~%float32 head_drop_ratio~%float32 baseline_ratio~%~%int32 consecutive_droop_frames~%time stamp~%~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'HeadPosture)))
  "Returns full string definition for message of type 'HeadPosture"
  (cl:format cl:nil "# Head posture evidence from the MediaPipe pose node.~%# Input to the fatigue monitor; does not trigger speech by itself.~%~%bool pose_visible~%bool calibrated~%bool head_down~%~%float32 posture_score~%float32 head_drop_ratio~%float32 baseline_ratio~%~%int32 consecutive_droop_frames~%time stamp~%~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <HeadPosture>))
  (cl:+ 0
     1
     1
     1
     4
     4
     4
     4
     8
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <HeadPosture>))
  "Converts a ROS message object to a list"
  (cl:list 'HeadPosture
    (cl:cons ':pose_visible (pose_visible msg))
    (cl:cons ':calibrated (calibrated msg))
    (cl:cons ':head_down (head_down msg))
    (cl:cons ':posture_score (posture_score msg))
    (cl:cons ':head_drop_ratio (head_drop_ratio msg))
    (cl:cons ':baseline_ratio (baseline_ratio msg))
    (cl:cons ':consecutive_droop_frames (consecutive_droop_frames msg))
    (cl:cons ':stamp (stamp msg))
))
