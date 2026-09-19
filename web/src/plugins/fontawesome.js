// Font Awesome (SVG, agac budamali): yalnizca burada kutuphaneye eklenen ikonlar pakete girer.
// Kullanim: <FaIcon icon="database" />  ya da  <FaIcon :icon="['far', 'circle']" />
import { library } from '@fortawesome/fontawesome-svg-core';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import {
  faBars, faBell, faBook, faBuilding, faBuildingUser, faChartPie, faChevronDown, faChevronLeft, faChevronRight,
  faCircleNodes, faClockRotateLeft, faComments, faCubes, faDatabase, faDiagramProject, faFileSignature,
  faGaugeHigh, faIdBadge, faLayerGroup, faLock, faMagnifyingGlass, faRightFromBracket, faScaleBalanced,
  faServer, faShieldHalved, faSitemap, faSliders, faTriangleExclamation, faUser, faUserShield, faUsers,
  faKeyboard, faCircleCheck, faCircleXmark, faSpinner, faPlus, faPenToSquare, faTrash, faXmark, faArrowRight,
  faSun, faMoon, faCircleHalfStroke, faListCheck, faKey, faArrowTrendUp, faClock, faFileLines, faBolt, faCircleInfo,
  faRotate, faArrowUpRightFromSquare, faFire, faCheckDouble,
  faDownload, faHourglassHalf, faCheck, faEnvelopeOpen, faInbox, faFileZipper, faFileWord, faEye, faEyeSlash, faGears,
  faFileExcel, faFileArrowUp, faFileArrowDown, faArrowsRotate,
  faFloppyDisk, faClone, faRotateLeft, faPowerOff, faWandMagicSparkles, faUserPlus, faUsersGear,
  faFileContract, faClipboardCheck, faIdCard, faCalendarDays, faUserCheck, faUserXmark, faUserSlash, faFileCircleCheck,
  faFileCircleExclamation, faFileCircleXmark, faSignature, faLink,
} from '@fortawesome/free-solid-svg-icons';
import { faCircle as farCircle } from '@fortawesome/free-regular-svg-icons';

library.add(
  faBars, faBell, faBook, faBuilding, faBuildingUser, faChartPie, faChevronDown, faChevronLeft, faChevronRight,
  faCircleNodes, faClockRotateLeft, faComments, faCubes, faDatabase, faDiagramProject, faFileSignature,
  faGaugeHigh, faIdBadge, faLayerGroup, faLock, faMagnifyingGlass, faRightFromBracket, faScaleBalanced,
  faServer, faShieldHalved, faSitemap, faSliders, faTriangleExclamation, faUser, faUserShield, faUsers,
  faKeyboard, faCircleCheck, faCircleXmark, faSpinner, faPlus, faPenToSquare, faTrash, faXmark, faArrowRight,
  faSun, faMoon, faCircleHalfStroke, faListCheck, faKey, faArrowTrendUp, faClock, faFileLines, faBolt, faCircleInfo,
  faRotate, faArrowUpRightFromSquare, faFire, faCheckDouble,
  faDownload, faHourglassHalf, faCheck, faEnvelopeOpen, faInbox, faFileZipper, faFileWord, faEye, faEyeSlash, faGears,
  faFileExcel, faFileArrowUp, faFileArrowDown, faArrowsRotate,
  faFloppyDisk, faClone, faRotateLeft, faPowerOff, faWandMagicSparkles, faUserPlus, faUsersGear,
  faFileContract, faClipboardCheck, faIdCard, faCalendarDays, faUserCheck, faUserXmark, faUserSlash, faFileCircleCheck,
  faFileCircleExclamation, faFileCircleXmark, faSignature, faLink,
  farCircle,
);

export { FontAwesomeIcon };
