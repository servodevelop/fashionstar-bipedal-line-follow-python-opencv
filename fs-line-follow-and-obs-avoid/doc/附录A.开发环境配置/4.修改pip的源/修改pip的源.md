# 修改pip的源



pip是用来管理Python包的工具.

如果不修改pip的源的话, 安装Python包的时候同样也会很慢.



进入用户主目录

```bash
cd
```

创建一个文件夹`.pip`

```
mkdir .pip
```

在文件夹`.pip`里面创建一个`pip.conf`文件

```
cd .pip
touch pip.conf
```

将下面文本内容复制到`~/.pip/pip.conf ` 里面

```
[global]
index-url = https://mirrors.ustc.edu.cn/pypi/web/simple
format = columns
```

然后在命令行里面执行一句

```
pip3
```

