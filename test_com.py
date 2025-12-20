import cv2

def test_camera():
    # 0 通常是内置摄像头，1 或 2 可能是外接 USB 摄像头
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("错误：无法打开摄像头。请检查虚拟机 USB 设置！")
        return

    print("摄像头已成功打开！按 'q' 键退出预览。")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("错误：无法接收画面帧。")
            break

        # 在窗口中显示画面
        cv2.imshow('Camera Test', frame)

        # 按 'q' 键退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_camera()
