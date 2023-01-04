import datetime
import io
import pyshorteners
import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from astropy.coordinates import SkyCoord
from sunpy.coordinates import frames
from solarmach import SolarMACH, print_body_list


# modify hamburger menu
about_info = '''
The *Solar MAgnetic Connection Haus* (**Solar-MACH**) tool is a multi-spacecraft longitudinal configuration plotter. It was originally developed at the University of Kiel, Germany, and further discussed within the ESA Heliophysics Archives USer (HAUS) group. Development takes now place at the University of Turku, Finland.

'''
get_help_link = "https://github.com/jgieseler/Solar-MACH/discussions"
report_bug_link = "https://github.com/jgieseler/Solar-MACH/discussions/4"
menu_items = {'About': about_info,
              'Get help': get_help_link,
              'Report a bug': report_bug_link}

# set page config - must be the first Streamlit command in the app
st.set_page_config(page_title='Solar-MACH', page_icon=":satellite:",
                   initial_sidebar_state="expanded",
                   menu_items=menu_items)

st.title('Solar-MACH')
st.header('Multi-spacecraft longitudinal configuration plotter')

st.warning("If your browser repeatedly complains about *redirecting too many times* or *redirecting not properly*, you might for the time being use [solar-mach.streamlitapp.com](https://solar-mach.streamlitapp.com) (instead of [solar-mach.github.io](https://solar-mach.github.io)).")  # Streamlit has recently changed some settings that still cause some problems. (Oct 2022)")

st.info("""
       📢 **Update 4 November 2022** 📢
       * Solar-MACH paper (preprint) available at [arXiv](https://arxiv.org/abs/2210.00819). Please cite this if you use Solar-MACH!
       * Added option to change between Carrington and Stonyhurst coordinates for the whole tool (deprecates overplotting of Earth-centered coordinate system)
       * Added option to change Earth position in the plot
       * Take into account solar differential rotation wrt. latitude (see [#21](https://github.com/jgieseler/solarmach/issues/21))
       * Instead of spherical radius, plot its projection to the heliographic equatorial plane (see [#3](https://github.com/jgieseler/solarmach/issues/3))
       """)

# Save parameters to URL for sharing and bookmarking
def make_url(set_query_params):
    st.experimental_set_query_params(**set_query_params)


def clear_url():
    """
    Clear parameters from URL bc. otherwise input becomes buggy as of Streamlit
    version 1.0. Will hopefully be fixed in the future. Then hopefully all
    occurences of "clear_url" can be removed.
    """
    st.experimental_set_query_params({'embedded': 'true'})


# obtain query paramamters from URL
query_params = st.experimental_get_query_params()

# define empty dict for new params to put into URL (only in box at the bottom)
set_query_params = {}

# catch old URL parameters and replace with current ones
if ("plot_reference" in query_params) and int(query_params["plot_reference"][0]) == 1:
    if "carr_long" in query_params and "carr_lat" in query_params and "reference_sys" in query_params and "coord_sys" not in query_params and int(query_params["reference_sys"][0]) == 0:
        query_params["reference_long"] = query_params.pop("carr_long")
        query_params["reference_lat"] = query_params.pop("carr_lat")
        query_params["coord_sys"] = query_params.pop("reference_sys")
        # query_params["coord_sys"] = ["0"]  # select Carrington coordinates
    elif "ston_long" in query_params and "ston_lat" in query_params and "reference_sys" in query_params and "coord_sys" not in query_params and int(query_params["reference_sys"][0]) == 1:
        query_params["reference_long"] = query_params.pop("ston_long")
        query_params["reference_lat"] = query_params.pop("ston_lat")
        query_params["coord_sys"] = query_params.pop("reference_sys")
        # query_params["coord_sys"] = ["1"]  # select Stonyhurst coordinates
    else:
        if "carr_long" in query_params or "carr_lat" in query_params or "ston_long" in query_params or "ston_lat" in query_params or "reference_sys" in query_params:
            st.error('⚠️ **WARNING:** Deprecated parameters have been prodived by the URL. To avoid unexpected behaviour, plotting of the reference has been deactivated!')
            query_params["plot_reference"][0] = 0

# saved obtained quety params from URL into session_state
for i in query_params:
    st.session_state[i] = query_params[i]

# removed as of now
# st.sidebar.button('Get shareable URL', help='Save parameters to URL, so that it can be saved or shared with others.', on_click=make_url, args=[set_query_params])

# provide date and time
with st.sidebar.container():
    # set starting parameters from URL if available, otherwise use defaults
    # def_d = datetime.datetime.strptime(query_params["date"][0], "%Y%m%d") if "date" in query_params \
    #         else datetime.date.today()-datetime.timedelta(days = 2)
    # def_t = datetime.datetime.strptime(query_params["time"][0], "%H%M") if "time" in query_params \
    #         else datetime.time(0, 0)
    def_d = datetime.datetime.strptime(st.session_state["date"][0], "%Y%m%d") if "date" in st.session_state else datetime.date.today()-datetime.timedelta(days=2)
    def_t = datetime.datetime.strptime(st.session_state["time"][0], "%H%M") if "time" in st.session_state else datetime.time(0, 0)
    d = st.sidebar.date_input("Select date", def_d)  # , on_change=clear_url)
    t = st.sidebar.time_input('Select time', def_t)  # , on_change=clear_url)
    date = datetime.datetime.combine(d, t).strftime("%Y-%m-%d %H:%M:%S")

    # save query parameters to URL
    sdate = d.strftime("%Y%m%d")
    stime = t.strftime("%H%M")
    set_query_params["date"] = [sdate]
    set_query_params["time"] = [stime]
    st.session_state["date"] = [sdate]
    st.session_state["time"] = [stime]


# plotting settings
with st.sidebar.container():
    coord_sys_list = ['Carrington', 'Stonyhurst']
    # set starting parameters from URL if available, otherwise use defaults
    # def_reference_sys = int(query_params["reference_sys"][0]) if "reference_sys" in query_params else 0
    def_coord_sys = int(st.session_state["coord_sys"][0]) if "coord_sys" in st.session_state else 0
    coord_sys = st.sidebar.radio('Coordinate system:', coord_sys_list, index=def_coord_sys, horizontal=True)
    set_query_params["coord_sys"] = [str(coord_sys_list.index(coord_sys))]
    st.session_state["coord_sys"] = [str(coord_sys_list.index(coord_sys))]

    st.sidebar.subheader('Plot options:')

    # if ("plot_spirals" in query_params) and int(query_params["plot_spirals"][0]) == 0:
    if ("plot_spirals" in st.session_state) and int(st.session_state["plot_spirals"][0]) == 0:
        def_plot_spirals = False
    else:
        def_plot_spirals = True
    plot_spirals = st.sidebar.checkbox('Parker spiral for each body', value=def_plot_spirals)  # , on_change=clear_url)
    if not plot_spirals:
        set_query_params["plot_spirals"] = [0]
        st.session_state["plot_spirals"] = [0]

    # if ("plot_sun_body_line" in query_params) and int(query_params["plot_sun_body_line"][0]) == 0:
    if ("plot_sun_body_line" in st.session_state) and int(st.session_state["plot_sun_body_line"][0]) == 0:
        def_plot_sun_body_line = False
    else:
        def_plot_sun_body_line = True
    plot_sun_body_line = st.sidebar.checkbox('Straight line from Sun to body', value=def_plot_sun_body_line)  # , on_change=clear_url)
    if not plot_sun_body_line:
        set_query_params["plot_sun_body_line"] = [0]
        st.session_state["plot_sun_body_line"] = [0]

    # # if ("plot_ecc" in query_params) and int(query_params["plot_ecc"][0]) == 1:
    # if ("plot_ecc" in st.session_state) and int(st.session_state["plot_ecc"][0]) == 1:
    #     def_show_earth_centered_coord = True
    # else:
    #     def_show_earth_centered_coord = False
    # show_earth_centered_coord = st.sidebar.checkbox('Add Stonyhurst coord. system', value=def_show_earth_centered_coord)  # , on_change=clear_url)
    # if show_earth_centered_coord:
    #     set_query_params["plot_ecc"] = [1]
    #     st.session_state["plot_ecc"] = [1]

    # if ("plot_trans" in query_params) and int(query_params["plot_trans"][0]) == 1:
    if ("plot_trans" in st.session_state) and int(st.session_state["plot_trans"][0]) == 1:
        def_transparent = True
    else:
        def_transparent = False
    transparent = st.sidebar.checkbox('Transparent background', value=def_transparent)  # , on_change=clear_url)
    if transparent:
        set_query_params["plot_trans"] = [1]
        st.session_state["plot_trans"] = [1]

    if ("plot_nr" in st.session_state) and int(st.session_state["plot_nr"][0]) == 1:
        def_numbered = True
    else:
        def_numbered = False
    numbered_markers = st.sidebar.checkbox('Numbered symbols', value=def_numbered)  # , on_change=clear_url)
    if numbered_markers:
        set_query_params["plot_nr"] = [1]
        st.session_state["plot_nr"] = [1]

    def_long_offset = int(st.session_state["long_offset"][0]) if "long_offset" in st.session_state else 270
    long_offset = int(st.sidebar.number_input('Plot Earth at longitude (axis system, 0=3 o`clock):', min_value=0, max_value=360, value=def_long_offset, step=90))
    set_query_params["long_offset"] = [str(int(long_offset))]
    st.session_state["long_offset"] = [str(int(long_offset))]

    # if ("plot_reference" in query_params) and int(query_params["plot_reference"][0]) == 1:
    if ("plot_reference" in st.session_state) and int(st.session_state["plot_reference"][0]) == 1:
        def_plot_reference = True
    else:
        def_plot_reference = False

    plot_reference = st.sidebar.checkbox('Plot reference (e.g. flare)', value=def_plot_reference)  # , on_change=clear_url)

    with st.sidebar.expander("Reference coordinates (e.g. flare)", expanded=plot_reference):
        wrong_ref_coord = False
        # reference_sys_list = ['Carrington', 'Stonyhurst']
        # # set starting parameters from URL if available, otherwise use defaults
        # # def_reference_sys = int(query_params["reference_sys"][0]) if "reference_sys" in query_params else 0
        # def_reference_sys = int(st.session_state["reference_sys"][0]) if "reference_sys" in st.session_state else 0
        # reference_sys = st.radio('Coordinate system:', reference_sys_list, index=def_reference_sys)

        def_reference_long = int(st.session_state["reference_long"][0]) if "reference_long" in st.session_state else 90
        def_reference_lat = int(st.session_state["reference_lat"][0]) if "reference_lat" in st.session_state else 0

        if coord_sys == 'Carrington':
            # def_reference_long = int(query_params["carr_long"][0]) if "carr_long" in query_params else 20
            # def_reference_lat = int(query_params["carr_lat"][0]) if "carr_lat" in query_params else 0
            # def_reference_long = int(st.session_state["carr_long"][0]) if "carr_long" in st.session_state else 20
            # def_reference_lat = int(st.session_state["carr_lat"][0]) if "carr_lat" in st.session_state else 0
            reference_long = st.number_input('Longitude (0 to 360):', min_value=0, max_value=360, value=def_reference_long)  # , on_change=clear_url)
            reference_lat = st.number_input('Latitude (-90 to 90):', min_value=-90, max_value=90, value=def_reference_lat)  # , on_change=clear_url)
            # outdated check for wrong coordinates (caught by using st.number_input)
            # if (reference_long < 0) or (reference_long > 360) or (reference_lat < -90) or (reference_lat > 90):
            #     wrong_ref_coord = True
            # if plot_reference is True:
            #     set_query_params["carr_long"] = [str(int(reference_long))]
            #     set_query_params["carr_lat"] = [str(int(reference_lat))]
            #     st.session_state["carr_long"] = [str(int(reference_long))]
            #     st.session_state["carr_lat"] = [str(int(reference_lat))]

        if coord_sys == 'Stonyhurst':
            # def_reference_long = int(query_params["ston_long"][0]) if "ston_long" in query_params else 90
            # def_reference_lat = int(query_params["ston_lat"][0]) if "ston_lat" in query_params else 0
            # def_reference_long = int(st.session_state["ston_long"][0]) if "ston_long" in st.session_state else 90
            # def_reference_lat = int(st.session_state["ston_lat"][0]) if "ston_lat" in st.session_state else 0
            # convert query coordinates (always Carrington) to Stonyhurst for input widget:
            # coord = SkyCoord(def_reference_long*u.deg, def_reference_lat*u.deg, frame=frames.HeliographicCarrington(observer='Sun', obstime=date))
            # coord = coord.transform_to(frames.HeliographicStonyhurst)
            # def_reference_long = coord.lon.value
            # def_reference_lat = coord.lat.value

            # read in coordinates from user
            reference_long = st.number_input('Longitude (-180 to 180, integer):', min_value=-180, max_value=180, value=def_reference_long)  # , on_change=clear_url)
            reference_lat = st.number_input('Latitude (-90 to 90, integer):', min_value=-90, max_value=90, value=def_reference_lat)  # , on_change=clear_url)
            # outdated check for wrong coordinates (caught by using st.number_input)
            # if (reference_long < -180) or (reference_long > 180) or (reference_lat < -90) or (reference_lat > 90):
            #     wrong_ref_coord = True
            # if plot_reference is True:
            #     set_query_params["ston_long"] = [str(int(reference_long))]
            #     set_query_params["ston_lat"] = [str(int(reference_lat))]
            #     st.session_state["ston_long"] = [str(int(reference_long))]
            #     st.session_state["ston_lat"] = [str(int(reference_lat))]

        if plot_reference is True:
            set_query_params["reference_long"] = [str(int(reference_long))]
            set_query_params["reference_lat"] = [str(int(reference_lat))]
            st.session_state["reference_long"] = [str(int(reference_long))]
            st.session_state["reference_lat"] = [str(int(reference_lat))]
        # outdated check for wrong coordinates (caught by using st.number_input)
        # if wrong_ref_coord:
        #         st.error('ERROR: There is something wrong in the prodived reference coordinates!')
        #         st.stop()

        # if reference_sys == 'Stonyhurst':
        #     # convert Stonyhurst coordinates to Carrington for further use:
        #     coord = SkyCoord(reference_long*u.deg, reference_lat*u.deg, frame=frames.HeliographicStonyhurst, obstime=date)
        #     coord = coord.transform_to(frames.HeliographicCarrington(observer='Sun'))
        #     reference_long = coord.lon.value
        #     reference_lat = coord.lat.value

        # import math
        # def_reference_vsw = int(query_params["reference_vsw"][0]) if "reference_vsw" in query_params else 400
        def_reference_vsw = int(st.session_state["reference_vsw"][0]) if "reference_vsw" in st.session_state else 400
        reference_vsw = st.number_input('Solar wind speed for reference (km/s)', min_value=0, value=def_reference_vsw, step=50)  # , on_change=clear_url)

    if plot_reference is False:
        reference_long = None
        reference_lat = None

    # save query parameters to URL
    if plot_reference is True:
        set_query_params["reference_vsw"] = [str(int(reference_vsw))]
        set_query_params["plot_reference"] = [1]
        st.session_state["reference_vsw"] = [str(int(reference_vsw))]
        st.session_state["plot_reference"] = [1]


st.sidebar.subheader('Choose bodies/spacecraft and measured solar wind speeds')
with st.sidebar.container():
    all_bodies = print_body_list()

    # rename L1 point and order body list alphabetically
    all_bodies = all_bodies.replace('SEMB-L1', 'L1')
    all_bodies = all_bodies.sort_index()

    # set starting parameters from URL if available, otherwise use defaults
    # def_full_body_list = query_params["bodies"] if "bodies" in query_params else ['STEREO A', 'Earth', 'BepiColombo', 'Parker Solar Probe', 'Solar Orbiter']
    # def_vsw_list = [int(i) for i in query_params["speeds"]] if "speeds" in query_params else [400, 400, 400, 400, 400]

    def_full_body_list = st.session_state["bodies"] if "bodies" in st.session_state else ['STEREO A', 'Earth', 'BepiColombo', 'Parker Solar Probe', 'Solar Orbiter']
    def_vsw_list = [int(i) for i in st.session_state["speeds"]] if "speeds" in st.session_state else [400, 400, 400, 400, 400]

    def_vsw_dict = {}
    for i in range(len(def_full_body_list)):
        try:
            def_vsw_dict[def_full_body_list[i]] = def_vsw_list[i]
        except IndexError:
            def_vsw_dict[def_full_body_list[i]] = 400

    body_list = st.multiselect(
        'Bodies/spacecraft',
        all_bodies,
        def_full_body_list,
        key='bodies')  # , on_change=clear_url)

    with st.sidebar.expander("Solar wind speed (kms/s) per S/C", expanded=True):
        vsw_dict = {}
        for body in body_list:
            vsw_dict[body] = int(st.number_input(body, min_value=0,
                                 value=def_vsw_dict.get(body, 400),
                                 step=50))  # , on_change=clear_url))
        vsw_list = [vsw_dict[body] for body in body_list]

    set_query_params["bodies"] = body_list
    set_query_params["speeds"] = vsw_list
    # st.session_state["bodies"] = body_list
    st.session_state["speeds"] = vsw_list

# url = 'http://localhost:8501/?'
# url = 'https://share.streamlit.io/jgieseler/solar-mach?'
# url = 'https://jgieseler-solar-mach-streamlit-app-aj6zer.streamlitapp.com/?embedded=true&'
url = 'https://solar-mach.streamlitapp.com/?embedded=true&'

for p in set_query_params:
    for i in set_query_params[p]:
        # st.write(str(p)+' '+str(i))
        url = url + str(p)+'='+str(i)+'&'
url = url.replace(' ', '+')

# possible alternative to using set_query_params dictionary:
# url2 = 'https://share.streamlit.io/jgieseler/solar-mach/testing/app.py?'
# for p in st.session_state:
#     for i in st.session_state[p]:
#         # st.write(str(p)+' '+str(i))
#         url2 = url2 + str(p)+'='+str(i)+'&'
# url2 = url2.replace(' ', '+')


if len(body_list) == len(vsw_list):
    # initialize the bodies
    c = SolarMACH(date, body_list, vsw_list, reference_long, reference_lat, coord_sys)

    # make the longitudinal constellation plot
    filename = 'Solar-MACH_'+datetime.datetime.combine(d, t).strftime("%Y-%m-%d_%H-%M-%S")

    c.plot(
        plot_spirals=plot_spirals,                            # plot Parker spirals for each body
        plot_sun_body_line=plot_sun_body_line,                # plot straight line between Sun and body
        reference_vsw=reference_vsw,                          # define solar wind speed at reference
        transparent=transparent,
        numbered_markers=numbered_markers,
        long_offset=long_offset,
        # outfile=filename+'.png'                               # output file (optional)
    )

    # download plot
    plot2 = io.BytesIO()
    plt.savefig(plot2, format='png', bbox_inches="tight")
    st.download_button(
        label="Download figure as .png file",
        data=plot2.getvalue(),
        file_name=filename+'.png',
        mime="image/png")

    # download plot, alternative. produces actual png image on server.
    # needs # outfile=filename+'.png' uncommented above
    # with open(filename+'.png', 'rb') as f:
    #     st.download_button('Download figure as .png file', f, file_name=filename+'.png', mime="image/png")

    # display coordinates table
    df = c.coord_table
    df.index = df['Spacecraft/Body']
    df = df.drop(columns=['Spacecraft/Body'])
    df = df.rename(columns={"Spacecraft/Body": "Spacecraft / body",
                            f"{coord_sys} longitude (°)": f"{coord_sys} longitude [°]",
                            f"{coord_sys} latitude (°)": f"{coord_sys} latitude [°]",
                            "Heliocentric distance (AU)": "Heliocent. distance [AU]",
                            "Longitudinal separation to Earth's longitude": "Longitud. separation to Earth longitude [°]",
                            "Latitudinal separation to Earth's latitude": "Latitud. separation to Earth latitude [°]",
                            "Vsw": "Solar wind speed [km/s]",
                            f"Magnetic footpoint longitude ({coord_sys})": f"Magnetic footpoint {coord_sys} longitude [°]",
                            "Longitudinal separation between body and reference_long": "Longitud. separation bw. body & reference [°]",
                            "Longitudinal separation between body's mangetic footpoint and reference_long": "Longitud. separation bw. body's magnetic footpoint & reference [°]",
                            "Latitudinal separation between body and reference_lat": "Latitudinal separation bw. body & reference [°]"})

    df2 = df.copy()
    decimals = 1
    df = df.round({f"{coord_sys} longitude [°]": decimals,
                   f"{coord_sys} latitude [°]": decimals,
                   "Longitud. separation to Earth longitude [°]": decimals,
                   "Latitud. separation to Earth latitude [°]": decimals,
                   "Solar wind speed [km/s]": decimals,
                   f"Magnetic footpoint {coord_sys} longitude [°]": decimals,
                   "Longitud. separation bw. body & reference [°]": decimals,
                   "Longitud. separation bw. body's magnetic footpoint & reference [°]": decimals,
                   "Latitudinal separation bw. body & reference [°]": decimals
                   }).astype(str)
    #               }).astype(np.int64).astype(str)  # yes, convert to int64 first and then to str to get rid of ".0" if using decimals=0
    df["Heliocent. distance [AU]"] = df2["Heliocent. distance [AU]"].round(2).astype(str)

    st.table(df.T)

    # download coordinates
    st.download_button(
        label="Download table as .csv file",
        data=c.coord_table.to_csv(index=False),
        file_name=filename+'.csv',
        mime='text/csv')
else:
    st.error(f"ERROR: Number of elements in the bodies/spacecraft list \
               ({len(body_list)}) and solar wind speed list ({len(vsw_list)}) \
               don't match! Please verify that for each body there is a solar \
               wind speed provided!")

st.markdown('###### Save or share this setup by bookmarking or distributing the following URL:')

st.info(url)

cont1 = st.container()


def get_short_url(url):
    """
    generate short da.gd URL
    """
    s = pyshorteners.Shortener()
    surl = s.dagd.short(url)
    # cont1.write(surl)
    cont1.success(surl)


cont1.button('Generate short URL', on_click=get_short_url, args=[url])

st.warning('''
           ⚠️ **NOTE: Because of changes to Streamlit, the URL format has changed in July 2022.** ⚠️
           * If you still have old URLs, you can update them by replacing "https://share.streamlit.io/jgieseler/solar-mach?" with "https://solar-mach.streamlitapp.com/?embedded=true&" (both without quotation marks).
           * In order to update a short URL that has been generated in the past, first get the full URL by adding "/coshorten" to it, e.g., https://da.gd/B95XM ⇒ https://da.gd/coshorten/B95XM. After that, you can update the URL like above.
           * Be aware that the new URL format might change in the near future again (hopefully to something more clear and permanent).
           ''')

# clear params from URL because Streamlit 1.0 still get some hickups when one
# changes the params; it then gets confused with the params in the URL and the
# one from the widgets.
clear_url()


# footer
st.markdown("""---""")

st.success('''
           📄 **Citation:** Please cite the following paper if you use Solar-MACH in your publication.

           *Gieseler, J., Dresing, N., Palmroos, C., von Forstner, J.L.F., Price, D.J., Vainio, R. et al. (2022).*
           *Solar-MACH: An open-source tool to analyze solar magnetic connection configurations. Frontiers in Astronomy and Space Physics (accepted).*
           *[arXiv:2210.00819](https://arxiv.org/abs/2210.00819)*
           ''')

st.markdown('The *Solar MAgnetic Connection Haus* (Solar-MACH) tool is a multi-spacecraft longitudinal configuration \
            plotter. It was originally developed at the University of Kiel, Germany, and further discussed within the \
            [ESA Heliophysics Archives USer (HAUS)](https://www.cosmos.esa.int/web/esdc/archives-user-groups/heliophysics) \
            group. Development takes now place at the University of Turku, Finland.')

st.markdown('For the full python package of Solar-MACH, refer to **solarmach**:<br>\
             [<img src="https://img.shields.io/static/v1?label=GitHub&message=solarmach&color=blue&logo=github" height="20">](https://github.com/jgieseler/solarmach/) \
             [<img src="https://img.shields.io/pypi/v/solarmach?style=flat&logo=pypi" height="20">](https://pypi.org/project/solarmach/) \
             [<img src="https://img.shields.io/conda/vn/conda-forge/solarmach?style=flat&logo=anaconda" height="20">](https://anaconda.org/conda-forge/solarmach/)', unsafe_allow_html=True)

st.markdown('For the Streamlit interface to the python package, refer to **Solar-MACH**:<br> \
             [<img src="https://img.shields.io/static/v1?label=GitHub&message=Solar-MACH&color=blue&logo=github" height="20">](https://github.com/jgieseler/Solar-MACH/) \
             [<img src="https://img.shields.io/static/v1?label=Contact&message=jan.gieseler@utu.fi&color=red&logo=gmail" height="20">](mailto:jan.gieseler@utu.fi?subject=Solar-MACH)', unsafe_allow_html=True)

col1, col2 = st.columns((5, 1))
col1.markdown("*The development of the online tool has received funding from the European Union's Horizon 2020 \
              research and innovation programme under grant agreement No 101004159 (SERPENTINE).*")
col2.markdown('[<img src="https://serpentine-h2020.eu/wp-content/uploads/2021/02/SERPENTINE_logo_new.png" \
                height="80">](https://serpentine-h2020.eu)', unsafe_allow_html=True)

st.markdown('Powered by: \
            [<img src="https://matplotlib.org/stable/_static/logo2_compressed.svg" height="25">](https://matplotlib.org) \
            [<img src="https://streamlit.io/images/brand/streamlit-logo-secondary-colormark-darktext.svg" height="30">](https://streamlit.io) \
            [<img src="https://raw.githubusercontent.com/sunpy/sunpy-logo/master/generated/sunpy_logo_landscape.svg" height="30">](https://sunpy.org)',
            unsafe_allow_html=True)


# remove 'Made with Streamlit' footer
# MainMenu {visibility: hidden;}
hide_streamlit_style = """
            <style>
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
