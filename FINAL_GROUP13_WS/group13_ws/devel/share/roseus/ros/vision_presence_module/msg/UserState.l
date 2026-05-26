;; Auto-generated. Do not edit!


(when (boundp 'vision_presence_module::UserState)
  (if (not (find-package "VISION_PRESENCE_MODULE"))
    (make-package "VISION_PRESENCE_MODULE"))
  (shadow 'UserState (find-package "VISION_PRESENCE_MODULE")))
(unless (find-package "VISION_PRESENCE_MODULE::USERSTATE")
  (make-package "VISION_PRESENCE_MODULE::USERSTATE"))

(in-package "ROS")
;;//! \htmlinclude UserState.msg.html


(defclass vision_presence_module::UserState
  :super ros::object
  :slots (_user_present _consecutive_eyes_missing _consecutive_face_absent _stamp ))

(defmethod vision_presence_module::UserState
  (:init
   (&key
    ((:user_present __user_present) nil)
    ((:consecutive_eyes_missing __consecutive_eyes_missing) 0)
    ((:consecutive_face_absent __consecutive_face_absent) 0)
    ((:stamp __stamp) (instance ros::time :init))
    )
   (send-super :init)
   (setq _user_present __user_present)
   (setq _consecutive_eyes_missing (round __consecutive_eyes_missing))
   (setq _consecutive_face_absent (round __consecutive_face_absent))
   (setq _stamp __stamp)
   self)
  (:user_present
   (&optional (__user_present :null))
   (if (not (eq __user_present :null)) (setq _user_present __user_present)) _user_present)
  (:consecutive_eyes_missing
   (&optional __consecutive_eyes_missing)
   (if __consecutive_eyes_missing (setq _consecutive_eyes_missing __consecutive_eyes_missing)) _consecutive_eyes_missing)
  (:consecutive_face_absent
   (&optional __consecutive_face_absent)
   (if __consecutive_face_absent (setq _consecutive_face_absent __consecutive_face_absent)) _consecutive_face_absent)
  (:stamp
   (&optional __stamp)
   (if __stamp (setq _stamp __stamp)) _stamp)
  (:serialization-length
   ()
   (+
    ;; bool _user_present
    1
    ;; int32 _consecutive_eyes_missing
    4
    ;; int32 _consecutive_face_absent
    4
    ;; time _stamp
    8
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; bool _user_present
       (if _user_present (write-byte -1 s) (write-byte 0 s))
     ;; int32 _consecutive_eyes_missing
       (write-long _consecutive_eyes_missing s)
     ;; int32 _consecutive_face_absent
       (write-long _consecutive_face_absent s)
     ;; time _stamp
       (write-long (send _stamp :sec) s) (write-long (send _stamp :nsec) s)
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; bool _user_present
     (setq _user_present (not (= 0 (sys::peek buf ptr- :char)))) (incf ptr- 1)
   ;; int32 _consecutive_eyes_missing
     (setq _consecutive_eyes_missing (sys::peek buf ptr- :integer)) (incf ptr- 4)
   ;; int32 _consecutive_face_absent
     (setq _consecutive_face_absent (sys::peek buf ptr- :integer)) (incf ptr- 4)
   ;; time _stamp
     (send _stamp :sec (sys::peek buf ptr- :integer)) (incf ptr- 4)  (send _stamp :nsec (sys::peek buf ptr- :integer)) (incf ptr- 4)
   ;;
   self)
  )

(setf (get vision_presence_module::UserState :md5sum-) "073fb340af5920b5f6f7b52a6f27778e")
(setf (get vision_presence_module::UserState :datatype-) "vision_presence_module/UserState")
(setf (get vision_presence_module::UserState :definition-)
      "bool  user_present
int32 consecutive_eyes_missing
int32 consecutive_face_absent
time  stamp

")



(provide :vision_presence_module/UserState "073fb340af5920b5f6f7b52a6f27778e")


